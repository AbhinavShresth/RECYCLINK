def register(client, email="ml@example.test"):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": "recyclink-test-password", "full_name": "ML User",
        "preferred_language": "en", "enable_recycler": False,
    })


def test_model_unavailable_is_explicit_and_no_prediction_is_created(client):
    response = client.get("/api/v1/ai/status")
    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert response.json()["status"] == "unavailable"
    assert register(client).status_code == 201
    no_csrf = client.post("/api/v1/ai/classify", files={"file": ("test.jpg", b"not-an-image", "image/jpeg")})
    assert no_csrf.status_code == 403
    rejected = client.post("/api/v1/ai/classify", files={"file": ("test.jpg", b"not-an-image", "image/jpeg")}, headers={"X-CSRF-Token": client.cookies["csrf_token"]})
    assert rejected.status_code == 400
    assert client.get("/api/v1/ai/history").json() == []


def test_classification_requires_authentication_and_mime_validation(client):
    response = client.post("/api/v1/ai/classify", files={"file": ("test.txt", b"x", "text/plain")})
    assert response.status_code == 401
    register(client)
    invalid = client.post("/api/v1/ai/classify", files={"file": ("test.txt", b"x", "text/plain")}, headers={"X-CSRF-Token": client.cookies["csrf_token"]})
    assert invalid.status_code == 415
