def register(client, email: str, *, recycler: bool = False):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "recyclink-test-password",
            "full_name": "Test Household",
            "enable_recycler": recycler,
            "roles": ["ADMIN"],
        },
    )


def csrf(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["csrf_token"]}


def test_registration_login_and_roles_are_server_derived(client):
    response = register(client, "Person@Example.test")
    assert response.status_code == 201
    assert response.json()["email"] == "person@example.test"
    assert response.json()["roles"] == ["USER"]
    cookie = response.headers["set-cookie"].lower()
    assert "recyclink_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/v1/auth/me").json()["roles"] == ["USER"]
    assert client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers=csrf(client)).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_saved_locations_are_private_and_csrf_protected(client):
    assert register(client, "owner@example.test").status_code == 201
    payload = {"label": "Home", "address": "Private demo address", "latitude": 28.6, "longitude": 77.2}
    rejected = client.post("/api/v1/users/me/locations", json=payload)
    assert rejected.status_code == 403
    created = client.post("/api/v1/users/me/locations", json=payload, headers=csrf(client))
    assert created.status_code == 201
    assert client.get("/api/v1/users/me/locations").json()[0]["address"] == payload["address"]

    from fastapi.testclient import TestClient

    second = TestClient(client.app)
    assert register(second, "other@example.test").status_code == 201
    assert second.get("/api/v1/users/me/locations").json() == []


def test_dual_role_capability_and_recycler_profile_validation(client):
    response = register(client, "dual@example.test", recycler=True)
    assert response.status_code == 201
    assert response.json()["roles"] == ["RECYCLER", "USER"]
    payload = {
        "business_name": "Reuse Cooperative",
        "min_pickup_grams": 500,
        "service_areas": [{"label": "Central", "center_latitude": 28.6, "center_longitude": 77.2, "radius_meters": 12000}],
        "accepted_categories": [{"category_code": "paper", "indicative_price_minor_per_kg": 2500}],
    }
    forbidden = client.put("/api/v1/recyclers/me", json=payload)
    assert forbidden.status_code == 403
    saved = client.put("/api/v1/recyclers/me", json=payload, headers=csrf(client))
    assert saved.status_code == 200
    assert saved.json()["accepted_categories"][0]["category_code"] == "paper"
    invalid = {**payload, "accepted_categories": [{"category_code": "unknown"}]}
    assert client.put("/api/v1/recyclers/me", json=invalid, headers=csrf(client)).status_code == 422
