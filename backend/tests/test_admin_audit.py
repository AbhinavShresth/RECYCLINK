from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.core.security import hash_password
from app.main import app
from app.models.identity import User, UserProfile, UserRole
from tests.test_marketplace import csrf, register


def test_audit_log_is_admin_only_and_omits_private_pickup_details(client):
    assert register(client, "audited-owner@example.test").status_code == 201
    created = client.post("/api/v1/listings", json={
        "category_code": "paper", "quantity_grams": 1250,
        "pickup_address": "Secret home address", "location": {"latitude": 28.61, "longitude": 77.21},
    }, headers=csrf(client))
    assert created.status_code == 201
    assert client.get("/api/v1/admin/audit-logs").status_code == 403

    override = app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    admin = User(email="audit-admin@example.test", password_hash=hash_password("recyclink-audit-password"))
    admin.profile = UserProfile(full_name="Audit Admin", preferred_language="en")
    admin.roles = [UserRole(role_code="ADMIN")]
    db.add(admin)
    db.commit()
    generator.close()

    admin_client = TestClient(client.app)
    login = admin_client.post("/api/v1/auth/login", json={"email": "audit-admin@example.test", "password": "recyclink-audit-password"})
    assert login.status_code == 200
    response = admin_client.get("/api/v1/admin/audit-logs?action=LISTING_CREATED")
    assert response.status_code == 200
    row = response.json()[0]
    assert row["entity_id"] == created.json()["id"]
    assert row["details"] == {"category_code": "paper", "quantity_grams": 1250}
    assert "Secret home address" not in response.text
