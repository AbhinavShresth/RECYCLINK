from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def csrf(client):
    return {"X-CSRF-Token": client.cookies["csrf_token"]}


def register(client, email, recycler=False):
    return client.post("/api/v1/auth/register", json={"email": email, "password": "recyclink-test-password", "full_name": "Recovery Test", "enable_recycler": recycler})


def make_collection(client):
    assert register(client, "waste-owner@example.test").status_code == 201
    listing = client.post("/api/v1/listings", json={"category_code":"paper", "quantity_grams":1200, "pickup_address":"A sample pickup location", "location":{"latitude":28.61,"longitude":77.21}}, headers=csrf(client)).json()
    recycler = TestClient(client.app)
    assert register(recycler, "recovery-recycler@example.test", True).status_code == 201
    profile = {"business_name":"Circular Recovery", "min_pickup_grams":100, "service_areas":[{"label":"Central","center_latitude":28.61,"center_longitude":77.21,"radius_meters":15000}], "accepted_categories":[{"category_code":"paper"}]}
    assert recycler.put("/api/v1/recyclers/me", json=profile, headers=csrf(recycler)).status_code == 200
    offer = recycler.post(f"/api/v1/listings/{listing['id']}/offers", json={"price_minor_per_kg":100}, headers=csrf(recycler)).json()
    collection = client.post(f"/api/v1/offers/{offer['id']}/accept", headers=csrf(client)).json()
    schedule = (datetime.now(UTC)+timedelta(days=1)).isoformat()
    collection_id=collection["id"]
    for payload in [{"status":"SCHEDULED","scheduled_at":schedule},{"status":"EN_ROUTE"},{"status":"ARRIVED"},{"status":"COLLECTED"},{"status":"WEIGHED","actual_quantity_grams":1000}]:
        result=recycler.post(f"/api/v1/collections/{collection_id}/transition",json=payload,headers=csrf(recycler))
        assert result.status_code==200,result.text
    return recycler,collection_id


def test_receipt_processing_mass_balance_sale_and_payment_confirmation(client):
    recycler,collection_id=make_collection(client)
    receipt=recycler.post("/api/v1/inventory/receipts",json={"collection_id":collection_id,"category_code":"paper","quantity_grams":1000},headers=csrf(recycler))
    assert receipt.status_code==201,receipt.text
    input_lot=receipt.json()["lot_id"]
    assert recycler.get("/api/v1/inventory").json()["total_available_grams"]==1000

    over_adjust=recycler.post("/api/v1/inventory/adjustments",json={"lot_id":input_lot,"quantity_delta_grams":-1100,"reason":"Incorrect count correction"},headers=csrf(recycler))
    assert over_adjust.status_code==409
    adjustment=recycler.post("/api/v1/inventory/adjustments",json={"lot_id":input_lot,"quantity_delta_grams":200,"reason":"Verified recount"},headers=csrf(recycler))
    assert adjustment.status_code==201 and adjustment.json()["new_balance_grams"]==1200

    batch=recycler.post("/api/v1/processing/batches",json={"process_type":"Manual sorting","inputs":[{"lot_id":input_lot,"quantity_grams":1000}],"outputs":[{"material_code":"plastic","quantity_grams":600,"quality_grade":"Sorted"}],"notes":"400 g residual/reject retained in batch balance"},headers=csrf(recycler))
    assert batch.status_code==201,batch.text
    assert batch.json()["residual_quantity_grams"]==400
    plastic_lot=batch.json()["outputs"][0]["lot_id"]
    totals={row["category_code"]:row["available_quantity_grams"] for row in recycler.get("/api/v1/inventory").json()["items"]}
    assert totals=={"paper":200,"plastic":600}

    oversell=recycler.post("/api/v1/transactions",json={"lot_id":plastic_lot,"quantity_grams":700,"unit_price_minor_per_kg":2200},headers=csrf(recycler))
    assert oversell.status_code==409
    sale=recycler.post("/api/v1/transactions",json={"lot_id":plastic_lot,"quantity_grams":500,"unit_price_minor_per_kg":2200,"buyer_reference":"Buyer reference 42"},headers=csrf(recycler))
    assert sale.status_code==201,sale.text
    transaction=sale.json()
    assert transaction["amount_minor"]==1100
    assert transaction["payment_status"]=="UNPAID"
    paid=recycler.post(f"/api/v1/transactions/{transaction['id']}/payment-confirmation",json={"payment_reference":"manual-confirm-42"},headers=csrf(recycler))
    assert paid.status_code==200
    assert paid.json()["payment_status"]=="PAID"
    assert paid.json()["payment_reference"]=="manual-confirm-42"
    assert len(recycler.get("/api/v1/inventory/ledger").json())==5


def test_processing_mass_cannot_exceed_input_and_cross_owner_lot_is_private(client):
    recycler,collection_id=make_collection(client)
    lot=recycler.post("/api/v1/inventory/receipts",json={"collection_id":collection_id,"category_code":"paper","quantity_grams":1000},headers=csrf(recycler)).json()["lot_id"]
    invalid=recycler.post("/api/v1/processing/batches",json={"process_type":"Sort","inputs":[{"lot_id":lot,"quantity_grams":500}],"outputs":[{"material_code":"plastic","quantity_grams":600}]},headers=csrf(recycler))
    assert invalid.status_code==422
    unrelated=TestClient(client.app)
    assert register(unrelated,"other-recovery@example.test",True).status_code==201
    assert unrelated.post("/api/v1/inventory/adjustments",json={"lot_id":lot,"quantity_delta_grams":10,"reason":"Should not be allowed"},headers=csrf(unrelated)).status_code==404
