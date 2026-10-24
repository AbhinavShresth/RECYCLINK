from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def register(client, email, recycler=False):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": "recyclink-test-password", "full_name": "Market Test",
        "preferred_language": "en", "enable_recycler": recycler,
    })


def csrf(client):
    return {"X-CSRF-Token": client.cookies["csrf_token"]}


def make_recycler(client, email):
    response = register(client, email, True)
    assert response.status_code == 201
    body = {
        "business_name": "North Loop Recovery", "min_pickup_grams": 100,
        "max_capacity_grams": 100000,
        "service_areas": [{"label": "Central", "center_latitude": 28.61, "center_longitude": 77.21, "radius_meters": 15000}],
        "accepted_categories": [{"category_code": "paper", "indicative_price_minor_per_kg": 2500}],
    }
    assert client.put("/api/v1/recyclers/me", json=body, headers=csrf(client)).status_code == 200


def test_listing_offer_accept_and_collection_lifecycle_with_address_privacy(client):
    assert register(client, "house@example.test").status_code == 201
    listing_response = client.post("/api/v1/listings", json={
        "category_code": "paper", "quantity_grams": 1500, "condition": "Dry and bundled",
        "description": "Cardboard boxes", "pickup_address": "12 Private Lane, Central",
        "location": {"latitude": 28.61, "longitude": 77.21},
    }, headers=csrf(client))
    assert listing_response.status_code == 201, listing_response.text
    listing = listing_response.json()
    assert listing["pickup_address"] == "12 Private Lane, Central"

    recycler = TestClient(client.app)
    make_recycler(recycler, "recycler@example.test")
    public_listing = recycler.get(f"/api/v1/listings/{listing['id']}").json()
    assert public_listing["pickup_address"] is None
    offer_response = recycler.post(f"/api/v1/listings/{listing['id']}/offers", json={
        "price_minor_per_kg": 2500, "pickup_fee_minor": 0,
        "proposed_pickup_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }, headers=csrf(recycler))
    assert offer_response.status_code == 201, offer_response.text

    accepted = client.post(f"/api/v1/offers/{offer_response.json()['id']}/accept", headers=csrf(client))
    assert accepted.status_code == 201, accepted.text
    collection = accepted.json()
    assert collection["status"] == "ACCEPTED"
    assert collection["estimated_quantity_grams"] == 1500
    assert collection["actual_quantity_grams"] is None
    private_after_acceptance = recycler.get(f"/api/v1/collections/{collection['id']}").json()
    assert private_after_acceptance["listing"]["pickup_address"] == "12 Private Lane, Central"

    invalid = client.post(f"/api/v1/collections/{collection['id']}/transition", json={"status": "COMPLETED"}, headers=csrf(client))
    assert invalid.status_code == 409
    scheduled_at = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    scheduled = recycler.post(f"/api/v1/collections/{collection['id']}/transition", json={"status": "SCHEDULED", "scheduled_at": scheduled_at}, headers=csrf(recycler))
    assert scheduled.status_code == 200
    for state in ["EN_ROUTE", "ARRIVED", "COLLECTED"]:
        result = recycler.post(f"/api/v1/collections/{collection['id']}/transition", json={"status": state}, headers=csrf(recycler))
        assert result.status_code == 200, result.text
    weighed = recycler.post(f"/api/v1/collections/{collection['id']}/transition", json={"status": "WEIGHED", "actual_quantity_grams": 1320}, headers=csrf(recycler))
    assert weighed.status_code == 200
    assert weighed.json()["estimated_quantity_grams"] == 1500
    assert weighed.json()["actual_quantity_grams"] == 1320
    done = recycler.post(f"/api/v1/collections/{collection['id']}/transition", json={"status": "COMPLETED"}, headers=csrf(recycler))
    assert done.status_code == 200
    assert done.json()["completed_at"] is not None
    assert len(done.json()["history"]) == 7


def test_recycler_cannot_offer_on_incompatible_or_out_of_area_listing(client):
    assert register(client, "seller@example.test").status_code == 201
    listing = client.post("/api/v1/listings", json={
        "category_code": "paper", "quantity_grams": 1000, "pickup_address": "Somewhere safe",
        "location": {"latitude": 10, "longitude": 10},
    }, headers=csrf(client)).json()
    recycler = TestClient(client.app)
    make_recycler(recycler, "far-recycler@example.test")
    result = recycler.post(f"/api/v1/listings/{listing['id']}/offers", json={"price_minor_per_kg": 100}, headers=csrf(recycler))
    assert result.status_code == 409


def test_other_account_cannot_accept_offer_or_read_private_collection(client):
    assert register(client, "first@example.test").status_code == 201
    listing = client.post("/api/v1/listings", json={
        "category_code": "paper", "quantity_grams": 1000, "pickup_address": "A private address",
        "location": {"latitude": 28.61, "longitude": 77.21},
    }, headers=csrf(client)).json()
    recycler = TestClient(client.app)
    make_recycler(recycler, "owning-recycler@example.test")
    offer = recycler.post(f"/api/v1/listings/{listing['id']}/offers", json={"price_minor_per_kg": 100}, headers=csrf(recycler)).json()
    collection = client.post(f"/api/v1/offers/{offer['id']}/accept", headers=csrf(client)).json()
    unrelated = TestClient(client.app)
    assert register(unrelated, "unrelated@example.test").status_code == 201
    assert unrelated.get(f"/api/v1/collections/{collection['id']}").status_code == 404
