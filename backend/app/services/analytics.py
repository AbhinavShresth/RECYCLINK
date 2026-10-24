from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bins import SmartBin
from app.models.classification import ClassificationFeedback, WasteClassification
from app.models.identity import User, UserRole
from app.models.marketplace import CollectionRequest, WasteListing
from app.models.recovery import (
    InventoryLedgerEntry,
    MaterialTransaction,
    ProcessingBatch,
    RecoveredMaterial,
)

COLLECTION_DONE = {"COMPLETED"}
COLLECTION_PENDING = {"ACCEPTED", "SCHEDULED", "ASSIGNED", "EN_ROUTE", "ARRIVED", "COLLECTED", "WEIGHED", "PROCESSING"}
COLLECTION_CANCELLED = {"CANCELLED", "DISPUTED"}


def _date_filter(query, field, start: datetime | None, end: datetime | None):
    if start:
        query = query.where(field >= start)
    if end:
        query = query.where(field < end)
    return query


def user_analytics(db: Session, user_id, start: datetime | None, end: datetime | None) -> dict:
    listings_q = _date_filter(select(WasteListing).where(WasteListing.owner_id == user_id), WasteListing.created_at, start, end)
    listings = db.scalars(listings_q).all()
    collections_q = _date_filter(select(CollectionRequest).where(CollectionRequest.user_id == user_id), CollectionRequest.created_at, start, end)
    collections = db.scalars(collections_q).all()
    categories: dict[str, int] = {}
    for listing in listings:
        categories[listing.category_code] = categories.get(listing.category_code, 0) + listing.quantity_grams
    complete = [c for c in collections if c.status in COLLECTION_DONE]
    pending = [c for c in collections if c.status in COLLECTION_PENDING]
    cancelled = [c for c in collections if c.status in COLLECTION_CANCELLED]
    actual = sum(c.actual_quantity_grams or 0 for c in complete)
    avg_turnaround = None
    durations = [(c.completed_at - c.created_at).total_seconds() / 3600 for c in complete if c.completed_at and c.created_at]
    if durations:
        avg_turnaround = round(sum(durations) / len(durations), 1)
    return {"period": {"start": start.isoformat() if start else None, "end_exclusive": end.isoformat() if end else None}, "listing_count": len(listings), "submitted_quantity_grams": sum(listing.quantity_grams for listing in listings), "collected_quantity_grams": actual, "completed_collections": len(complete), "pending_collections": len(pending), "cancelled_or_disputed_collections": len(cancelled), "average_turnaround_hours": avg_turnaround, "category_quantities_grams": categories, "calculated_at": datetime.now(UTC).isoformat(), "definitions": {"submitted": "Sum of listing estimates created in the selected period.", "collected": "Sum of actual weighed quantities for completed collections created in the selected period.", "pending": "Accepted through processing collection states; draft/open listings are not collections."}}


def recycler_analytics(db: Session, user_id, start: datetime | None, end: datetime | None) -> dict:
    collections_q = _date_filter(select(CollectionRequest).where(CollectionRequest.recycler_id == user_id), CollectionRequest.created_at, start, end)
    collections = db.scalars(collections_q).all()
    transactions_q = _date_filter(select(MaterialTransaction).where(MaterialTransaction.recycler_id == user_id), MaterialTransaction.created_at, start, end)
    transactions = db.scalars(transactions_q).all()
    recovered_q = _date_filter(select(RecoveredMaterial).join(ProcessingBatch, RecoveredMaterial.batch_id == ProcessingBatch.id).where(ProcessingBatch.recycler_id == user_id), ProcessingBatch.created_at, start, end)
    recovered = db.scalars(recovered_q).all()
    ledger_q = _date_filter(select(InventoryLedgerEntry).where(InventoryLedgerEntry.recycler_id == user_id), InventoryLedgerEntry.created_at, start, end)
    ledger = db.scalars(ledger_q).all()
    done = [c for c in collections if c.status == "COMPLETED"]
    closed_eligible = [c for c in collections if c.status in COLLECTION_DONE | COLLECTION_CANCELLED]
    completed = len(done)
    turnaround = [(c.completed_at - c.created_at).total_seconds() / 3600 for c in done if c.completed_at]
    inventory_delta: dict[str, int] = {}
    for entry in ledger:
        # These deltas are period movements, not current on-hand balances.
        inventory_delta[entry.movement_type] = inventory_delta.get(entry.movement_type, 0) + entry.quantity_delta_grams
    revenue = sum(t.amount_minor for t in transactions)
    paid = sum(t.amount_minor for t in transactions if t.payment_status == "PAID")
    return {"period": {"start": start.isoformat() if start else None, "end_exclusive": end.isoformat() if end else None}, "collections_received": len(collections), "completed_collections": completed, "cancelled_or_disputed_collections": sum(c.status in COLLECTION_CANCELLED for c in collections), "completion_rate": round(completed / len(closed_eligible), 4) if closed_eligible else None, "average_turnaround_hours": round(sum(turnaround) / len(turnaround), 1) if turnaround else None, "actual_collected_quantity_grams": sum(c.actual_quantity_grams or 0 for c in done), "inventory_movements_grams_by_type": inventory_delta, "recorded_recovered_quantity_grams": sum(r.quantity_grams for r in recovered), "sales_value_minor_inr": revenue, "paid_sales_value_minor_inr": paid, "unpaid_sales_value_minor_inr": revenue - paid, "transaction_count": len(transactions), "calculated_at": datetime.now(UTC).isoformat(), "definitions": {"completion_rate": "Completed collections / collections that are completed, cancelled, or disputed in this period; pending collections excluded.", "sales_value": "Sum of recorded material sale transactions, not offer estimates. Currency is INR minor units (paise).", "recovered": "Recorded processing output only; collection weight is not treated as recovered material."}}


def admin_analytics(db: Session, start: datetime | None, end: datetime | None) -> dict:
    users = db.scalars(select(User).where(User.is_active.is_(True))).all()
    user_roles = db.scalars(select(UserRole)).all()
    by_role: dict[str, int] = {}
    for role in user_roles:
        if role.user_id in {u.id for u in users}:
            by_role[role.role_code] = by_role.get(role.role_code, 0) + 1
    listing_q = _date_filter(select(WasteListing), WasteListing.created_at, start, end)
    listings = db.scalars(listing_q).all()
    collections_q = _date_filter(select(CollectionRequest), CollectionRequest.created_at, start, end)
    collections = db.scalars(collections_q).all()
    classifications_q = _date_filter(select(WasteClassification), WasteClassification.created_at, start, end)
    classifications = db.scalars(classifications_q).all()
    feedback_q = _date_filter(select(ClassificationFeedback), ClassificationFeedback.created_at, start, end)
    feedback = db.scalars(feedback_q).all()
    recovered_q = _date_filter(select(RecoveredMaterial).join(ProcessingBatch, RecoveredMaterial.batch_id == ProcessingBatch.id), ProcessingBatch.created_at, start, end)
    recovered = db.scalars(recovered_q).all()
    roles_admin = by_role.get("ADMIN", 0)
    predicted = {c.id: c.predicted_class for c in classifications}
    category_quantities: dict[str, int] = {}
    for listing in listings:
        category_quantities[listing.category_code] = category_quantities.get(listing.category_code, 0) + listing.quantity_grams
    return {"period": {"start": start.isoformat() if start else None, "end_exclusive": end.isoformat() if end else None}, "active_users": len(users), "active_recyclers": by_role.get("RECYCLER", 0), "administrators": roles_admin, "listings_created": len(listings), "open_listings": sum(listing.status == "OPEN" for listing in listings), "category_quantities_grams": category_quantities, "collections_by_status": _count(c.status for c in collections), "reported_quantity_grams": sum(listing.quantity_grams for listing in listings), "collected_quantity_grams": sum(c.actual_quantity_grams or 0 for c in collections if c.status == "COMPLETED"), "processed_input_quantity_grams": _processing_input_total(db, start, end), "recorded_recovered_quantity_grams": sum(r.quantity_grams for r in recovered), "classification_count": len(classifications), "uncertain_classification_count": sum(c.needs_confirmation for c in classifications), "classification_feedback_count": len(feedback), "classification_corrections": sum(f.confirmed_class != predicted.get(f.classification_id, f.confirmed_class) for f in feedback), "simulated_bins": db.scalar(select(func.count()).select_from(SmartBin).where(SmartBin.sensor_source == "SIMULATED")) or 0, "calculated_at": datetime.now(UTC).isoformat(), "definitions": {"reported": "Listing estimates created during the selected period.", "collected": "Actual weights on completed collections created during the selected period.", "processed": "Input weights recorded in processing batches during the selected period.", "recovered": "Recorded outputs from processing batches; not inferred from collected quantities.", "correction_rate": "Corrected reviewed classifications / all reviewed classifications; a zero denominator is reported as counts only."}}


def _count(values) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def _processing_input_total(db: Session, start: datetime | None, end: datetime | None) -> int:
    query = _date_filter(select(func.coalesce(func.sum(ProcessingBatch.input_quantity_grams), 0)), ProcessingBatch.created_at, start, end)
    return int(db.scalar(query) or 0)
