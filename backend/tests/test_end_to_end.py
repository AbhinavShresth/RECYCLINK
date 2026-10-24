from tests.test_marketplace import csrf
from tests.test_recovery import make_collection


def test_collection_recovery_and_analytics_reconcile(client):
    recycler, collection_id = make_collection(client)
    completed = recycler.post(f"/api/v1/collections/{collection_id}/transition", json={"status": "COMPLETED"}, headers=csrf(recycler))
    assert completed.status_code == 200

    user_metrics = client.get("/api/v1/analytics/user").json()
    recycler_metrics = recycler.get("/api/v1/analytics/recycler").json()
    assert user_metrics["submitted_quantity_grams"] == 1200
    assert user_metrics["collected_quantity_grams"] == 1000
    assert recycler_metrics["actual_collected_quantity_grams"] == 1000
    assert recycler_metrics["completion_rate"] == 1.0

    receipt = recycler.post("/api/v1/inventory/receipts", json={"collection_id": collection_id, "category_code": "paper", "quantity_grams": 1000}, headers=csrf(recycler))
    assert receipt.status_code == 201
    batch = recycler.post("/api/v1/processing/batches", json={"process_type": "Sorting", "inputs": [{"lot_id": receipt.json()["lot_id"], "quantity_grams": 1000}], "outputs": [{"material_code": "plastic", "quantity_grams": 700}]}, headers=csrf(recycler))
    assert batch.status_code == 201
    assert batch.json()["residual_quantity_grams"] == 300
    recovered_metrics = recycler.get("/api/v1/analytics/recycler").json()
    assert recovered_metrics["recorded_recovered_quantity_grams"] == 700

    output_lot = batch.json()["outputs"][0]["lot_id"]
    sale = recycler.post("/api/v1/transactions", json={"lot_id": output_lot, "quantity_grams": 400, "unit_price_minor_per_kg": 2200}, headers=csrf(recycler))
    assert sale.status_code == 201
    financial = recycler.get("/api/v1/analytics/recycler").json()
    assert financial["sales_value_minor_inr"] == 880
    assert financial["paid_sales_value_minor_inr"] == 0
