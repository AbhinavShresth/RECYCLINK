from types import SimpleNamespace

from app.api.v1 import voice
from tests.test_marketplace import csrf, make_recycler, register


def test_recycler_discovery_filters_material_quantity_and_service_area(client):
    make_recycler(client, "discover-recycler@example.test")
    result = client.get("/api/v1/recyclers/discover?category=paper&latitude=28.61&longitude=77.21&quantity_grams=1000")
    assert result.status_code == 200
    assert len(result.json()) == 1
    row = result.json()[0]
    assert row["business_name"] == "North Loop Recovery"
    assert row["distance_metric"] == "STRAIGHT_LINE_SERVICE_AREA_FILTER"
    assert row["straight_line_distance_meters"] == 0
    assert client.get("/api/v1/recyclers/discover?category=plastic&latitude=28.61&longitude=77.21&quantity_grams=1000").json() == []
    assert client.get("/api/v1/recyclers/discover?category=paper&latitude=0&longitude=0&quantity_grams=1000").json() == []


def test_voice_unconfigured_is_explicit_and_session_does_not_fake_connection(client):
    unauthenticated = client.get("/api/v1/voice/status")
    assert unauthenticated.status_code == 401
    assert register(client, "voice-user@example.test").status_code == 201
    status = client.get("/api/v1/voice/status")
    assert status.status_code == 200
    assert status.json()["configured"] is False
    session = client.post("/api/v1/voice/session", headers=csrf(client))
    assert session.status_code == 503
    assert "not configured" in session.json()["detail"]


def test_voice_session_uses_server_key_and_returns_only_temporary_url(client, monkeypatch):
    assert register(client, "configured-voice@example.test").status_code == 201
    monkeypatch.setattr(voice, "get_settings", lambda: SimpleNamespace(elevenlabs_api_key="server-secret", elevenlabs_agent_id="agent-demo", elevenlabs_api_base_url="https://api.elevenlabs.io/v1"))

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"signed_url": "wss://api.elevenlabs.io/v1/convai/conversation?temporary=token"}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, *, params, headers):
            assert url == "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
            assert params == {"agent_id": "agent-demo"}
            assert headers == {"xi-api-key": "server-secret"}
            return Response()

    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **_kwargs: Client())
    result = client.post("/api/v1/voice/session", headers=csrf(client))
    assert result.status_code == 200
    assert result.json()["signed_url"].startswith("wss://")
    assert "server-secret" not in result.text
