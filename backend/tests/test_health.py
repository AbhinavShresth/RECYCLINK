from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_is_independent_of_optional_providers() -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["service"] == "recyclink-api"


def test_readiness_checks_configured_database() -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
