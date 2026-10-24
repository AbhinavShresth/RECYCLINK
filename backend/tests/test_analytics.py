from tests.test_marketplace import csrf, register


def test_user_analytics_is_owned_and_empty_state_is_real(client):
    assert register(client, "analytics-user@example.test").status_code == 201
    empty = client.get("/api/v1/analytics/user")
    assert empty.status_code == 200
    assert empty.json()["listing_count"] == 0
    assert empty.json()["submitted_quantity_grams"] == 0

    listing = client.post("/api/v1/listings", json={
        "category_code": "paper", "quantity_grams": 2400,
        "pickup_address": "Private address", "location": {"latitude": 28.61, "longitude": 77.21},
    }, headers=csrf(client))
    assert listing.status_code == 201
    own = client.get("/api/v1/analytics/user").json()
    assert own["listing_count"] == 1
    assert own["submitted_quantity_grams"] == 2400
    assert own["category_quantities_grams"] == {"paper": 2400}

    other = type(client)(client.app)
    assert register(other, "other-analytics@example.test").status_code == 201
    theirs = other.get("/api/v1/analytics/user").json()
    assert theirs["listing_count"] == 0
    assert theirs["submitted_quantity_grams"] == 0


def test_analytics_date_range_and_role_authorization(client):
    assert register(client, "date-analytics@example.test").status_code == 201
    invalid = client.get("/api/v1/analytics/user?start=2026-05-02T00:00:00Z&end=2026-05-01T00:00:00Z")
    assert invalid.status_code == 422
    assert client.get("/api/v1/analytics/recycler").status_code == 403
    assert client.get("/api/v1/analytics/admin").status_code == 403
