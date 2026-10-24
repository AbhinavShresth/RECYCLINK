import pytest

from app.routing.optimizer import optimize
from app.routing.osrm import OSRMProvider, Point


def test_nearest_neighbor_and_two_opt_improve_shared_road_duration_objective():
    # Index 0=start, 1/2=stops, 3=end. Input order is deliberately poor.
    matrix = [
        [0, 1, 2, 10],
        [1, 0, 100, 1],
        [2, 1, 0, 2],
        [10, 1, 2, 0],
    ]
    result = optimize(matrix, 2)
    assert result["baseline_order"] == [0, 1, 2, 3]
    assert result["optimized_order"] == [0, 2, 1, 3]
    assert result["optimized_duration_seconds"] < result["baseline_duration_seconds"]
    assert "not globally optimal" in result["method"]


def test_optimizer_rejects_incomplete_or_unreachable_matrix():
    with pytest.raises(ValueError, match="dimensions"):
        optimize([[0, 1], [1, 0]], 1)
    with pytest.raises(ValueError, match="unreachable"):
        optimize([[0, None, 1], [1, 0, 1], [1, 1, 0]], 1)


def test_osrm_provider_sends_ordered_lon_lat_coordinates(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"code": "Ok", "durations": [[0, 1], [2, 0]], "distances": [[0, 3], [4, 0]]}

    def fake_get(url, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return Response()

    monkeypatch.setattr("app.routing.osrm.httpx.get", fake_get)
    result = OSRMProvider("http://router.local/", timeout=3).table([Point(28.6, 77.2), Point(28.7, 77.3)])
    assert captured["url"].endswith("/table/v1/driving/77.200000,28.600000;77.300000,28.700000")
    assert captured["params"]["annotations"] == "distance,duration"
    assert result["durations"][0][1] == 1


def test_osrm_successful_matrix_is_cached(monkeypatch):
    count = 0

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"code": "Ok", "durations": [[0]], "distances": [[0]]}

    def fake_get(*args, **kwargs):
        nonlocal count
        count += 1
        return Response()

    monkeypatch.setattr("app.routing.osrm.httpx.get", fake_get)
    provider = OSRMProvider("http://cache-test.local")
    point = [Point(0, 0)]
    provider.table(point)
    provider.table(point)
    assert count == 1


def test_route_api_reports_missing_provider_and_role(client):
    from fastapi.testclient import TestClient

    user = client.post("/api/v1/auth/register", json={"email":"regular-route@example.test", "password":"recyclink-test-password", "full_name":"Route User"})
    assert user.status_code == 201
    payload = {"start": {"latitude": 28.6, "longitude": 77.2}, "stop_collection_ids": ["123e4567-e89b-42d3-a456-426614174000"]}
    assert client.post("/api/v1/routes/optimize", json=payload, headers={"X-CSRF-Token": client.cookies["csrf_token"]}).status_code == 403
    recycler = TestClient(client.app)
    assert recycler.post("/api/v1/auth/register", json={"email":"route-recycler@example.test", "password":"recyclink-test-password", "full_name":"Route Recycler", "enable_recycler":True}).status_code == 201
    no_csrf = recycler.post("/api/v1/routes/optimize", json=payload)
    assert no_csrf.status_code == 403
    unavailable = recycler.post("/api/v1/routes/optimize", json=payload, headers={"X-CSRF-Token": recycler.cookies["csrf_token"]})
    assert unavailable.status_code == 503
    assert "OSRM_BASE_URL" in unavailable.json()["detail"]
