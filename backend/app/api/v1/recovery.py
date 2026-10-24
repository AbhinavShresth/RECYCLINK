from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_csrf, require_roles
from app.db.session import get_db
from app.models.identity import User, WasteCategory
from app.models.marketplace import CollectionRequest, WasteListing
from app.models.recovery import (
    InventoryLedgerEntry,
    InventoryLot,
    MaterialTransaction,
    ProcessingBatch,
    ProcessingInput,
    RecoveredMaterial,
    TransactionStatusEvent,
)
from app.schemas.recovery import (
    InventoryAdjustmentIn,
    InventoryReceiptIn,
    MaterialSaleCreate,
    PaymentConfirmIn,
    ProcessingBatchCreate,
)
from app.services.audit import record_audit

router = APIRouter(tags=["inventory, processing, and transactions"])


def inventory_balance(db: Session, lot_id: UUID) -> int:
    return int(db.scalar(select(func.coalesce(func.sum(InventoryLedgerEntry.quantity_delta_grams), 0)).where(InventoryLedgerEntry.lot_id == lot_id)) or 0)


def transaction_view(row: MaterialTransaction) -> dict:
    return {"id": str(row.id), "lot_id": str(row.lot_id), "material_code": row.material_code, "quantity_grams": row.quantity_grams, "unit_price_minor_per_kg": row.unit_price_minor_per_kg, "amount_minor": row.amount_minor, "currency": row.currency, "buyer_reference": row.buyer_reference, "payment_status": row.payment_status, "payment_reference": row.payment_reference, "payment_confirmed_at": row.payment_confirmed_at.isoformat() if row.payment_confirmed_at else None, "created_at": row.created_at.isoformat()}


@router.get("/inventory")
def inventory_summary(db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    rows = db.execute(select(InventoryLot.category_code, func.sum(InventoryLedgerEntry.quantity_delta_grams)).join(InventoryLedgerEntry, InventoryLedgerEntry.lot_id == InventoryLot.id).where(InventoryLot.recycler_id == user.id).group_by(InventoryLot.category_code)).all()
    balances = [{"category_code": category, "available_quantity_grams": int(balance or 0)} for category, balance in rows if int(balance or 0) != 0]
    return {"items": balances, "total_available_grams": sum(row["available_quantity_grams"] for row in balances), "unit": "grams", "calculated_at": datetime.now(UTC).isoformat(), "valuation": "Not calculated; no inventory cost valuation policy is configured."}


@router.get("/inventory/ledger")
def inventory_ledger(db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> list[dict]:
    entries = db.scalars(select(InventoryLedgerEntry).where(InventoryLedgerEntry.recycler_id == user.id).order_by(InventoryLedgerEntry.created_at.desc()).limit(200)).all()
    result = []
    for entry in entries:
        lot = db.get(InventoryLot, entry.lot_id)
        result.append({"id": str(entry.id), "lot_id": str(entry.lot_id), "category_code": lot.category_code, "quantity_delta_grams": entry.quantity_delta_grams, "movement_type": entry.movement_type, "reason": entry.reason, "collection_id": str(entry.collection_id) if entry.collection_id else None, "processing_batch_id": str(entry.processing_batch_id) if entry.processing_batch_id else None, "transaction_id": str(entry.transaction_id) if entry.transaction_id else None, "created_at": entry.created_at.isoformat()})
    return result


@router.get("/inventory/lots")
def inventory_lots(db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> list[dict]:
    lots = db.scalars(select(InventoryLot).where(InventoryLot.recycler_id == user.id).order_by(InventoryLot.created_at.desc()).limit(200)).all()
    result = []
    for lot in lots:
        balance = inventory_balance(db, lot.id)
        if balance > 0:
            result.append({"id": str(lot.id), "category_code": lot.category_code, "available_quantity_grams": balance, "origin_collection_id": str(lot.origin_collection_id) if lot.origin_collection_id else None, "source_batch_id": str(lot.source_batch_id) if lot.source_batch_id else None, "location_label": lot.location_label, "created_at": lot.created_at.isoformat()})
    return result


@router.post("/inventory/receipts", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def receive_material(payload: InventoryReceiptIn, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    category = db.get(WasteCategory, payload.category_code)
    if category is None or not category.is_active:
        raise HTTPException(422, "Choose an available material category")
    collection = db.scalar(select(CollectionRequest).where(CollectionRequest.id == payload.collection_id, CollectionRequest.recycler_id == user.id).with_for_update())
    if collection is None:
        raise HTTPException(404, "Weighed collection not found")
    if collection.status not in {"WEIGHED", "PROCESSING", "COMPLETED"} or collection.actual_quantity_grams is None:
        raise HTTPException(409, "Record the actual collected quantity before facility receipt")
    listing = db.get(WasteListing, collection.listing_id)
    differs = payload.quantity_grams != collection.actual_quantity_grams or payload.category_code != listing.category_code
    if differs and not payload.difference_reason:
        raise HTTPException(422, "Explain the material or quantity difference from collection records")
    lot = InventoryLot(recycler_id=user.id, category_code=payload.category_code, origin_collection_id=collection.id, initial_quantity_grams=payload.quantity_grams, location_label=payload.location_label, acquired_cost_minor=payload.acquired_cost_minor)
    db.add(lot)
    db.flush()
    db.add(InventoryLedgerEntry(lot_id=lot.id, recycler_id=user.id, quantity_delta_grams=payload.quantity_grams, movement_type="RECEIVED", reason=payload.difference_reason or "Facility receipt from completed collection", collection_id=collection.id, actor_id=user.id))
    record_audit(db, user.id, "INVENTORY_RECEIVED", "inventory_lot", lot.id, {"collection_id": str(collection.id), "category_code": lot.category_code, "quantity_grams": lot.initial_quantity_grams})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This collection has already been received into inventory") from None
    return {"lot_id": str(lot.id), "collection_id": str(collection.id), "category_code": lot.category_code, "quantity_grams": lot.initial_quantity_grams, "movement_type": "RECEIVED"}


@router.post("/inventory/adjustments", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def adjust_inventory(payload: InventoryAdjustmentIn, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    lot = db.scalar(select(InventoryLot).where(InventoryLot.id == payload.lot_id, InventoryLot.recycler_id == user.id).with_for_update())
    if lot is None:
        raise HTTPException(404, "Inventory lot not found")
    balance = inventory_balance(db, lot.id)
    new_balance = balance + payload.quantity_delta_grams
    if new_balance < 0:
        raise HTTPException(409, f"Adjustment exceeds available inventory ({balance} grams)")
    entry = InventoryLedgerEntry(lot_id=lot.id, recycler_id=user.id, quantity_delta_grams=payload.quantity_delta_grams, movement_type="ADJUSTMENT", reason=payload.reason, actor_id=user.id)
    db.add(entry)
    record_audit(db, user.id, "INVENTORY_ADJUSTED", "inventory_lot", lot.id, {"quantity_delta_grams": payload.quantity_delta_grams})
    db.commit()
    return {"movement_id": str(entry.id), "lot_id": str(lot.id), "new_balance_grams": new_balance}


@router.post("/processing/batches", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def create_processing_batch(payload: ProcessingBatchCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    categories = {row.material_code for row in payload.outputs}
    valid_codes = set(db.scalars(select(WasteCategory.code).where(WasteCategory.code.in_(categories), WasteCategory.is_active)).all())
    if categories != valid_codes:
        raise HTTPException(422, "A recovered output has an unknown or inactive category")
    lot_ids = sorted({item.lot_id for item in payload.inputs}, key=str)
    lots = db.scalars(select(InventoryLot).where(InventoryLot.id.in_(lot_ids), InventoryLot.recycler_id == user.id).order_by(InventoryLot.id).with_for_update()).all()
    by_id = {lot.id: lot for lot in lots}
    if len(by_id) != len(lot_ids):
        raise HTTPException(404, "One or more input lots are unavailable to this recycler")
    for item in payload.inputs:
        balance = inventory_balance(db, item.lot_id)
        if item.quantity_grams > balance:
            raise HTTPException(409, f"Input quantity exceeds available stock ({balance} grams)")
    input_total = sum(item.quantity_grams for item in payload.inputs)
    recovered_total = sum(item.quantity_grams for item in payload.outputs)
    residual = input_total - recovered_total
    batch = ProcessingBatch(recycler_id=user.id, process_type=payload.process_type.strip(), input_quantity_grams=input_total, recovered_quantity_grams=recovered_total, residual_quantity_grams=residual, notes=payload.notes)
    db.add(batch)
    db.flush()
    recovered_lots = []
    for item in payload.inputs:
        db.add(ProcessingInput(batch_id=batch.id, lot_id=item.lot_id, quantity_grams=item.quantity_grams))
        db.add(InventoryLedgerEntry(lot_id=item.lot_id, recycler_id=user.id, quantity_delta_grams=-item.quantity_grams, movement_type="PROCESSED", reason=f"Input to processing batch {batch.id}", processing_batch_id=batch.id, actor_id=user.id))
    for output in payload.outputs:
        lot = InventoryLot(recycler_id=user.id, category_code=output.material_code, source_batch_id=batch.id, initial_quantity_grams=output.quantity_grams)
        db.add(lot)
        db.flush()
        db.add(RecoveredMaterial(batch_id=batch.id, lot_id=lot.id, material_code=output.material_code, quantity_grams=output.quantity_grams, quality_grade=output.quality_grade))
        db.add(InventoryLedgerEntry(lot_id=lot.id, recycler_id=user.id, quantity_delta_grams=output.quantity_grams, movement_type="RECOVERED", reason=f"Output from processing batch {batch.id}", processing_batch_id=batch.id, actor_id=user.id))
        recovered_lots.append({"lot_id": str(lot.id), "material_code": output.material_code, "quantity_grams": output.quantity_grams})
    record_audit(db, user.id, "PROCESSING_RECORDED", "processing_batch", batch.id, {"input_quantity_grams": input_total, "recovered_quantity_grams": recovered_total, "residual_quantity_grams": residual})
    db.commit()
    return {"batch_id": str(batch.id), "process_type": batch.process_type, "input_quantity_grams": input_total, "recovered_quantity_grams": recovered_total, "residual_quantity_grams": residual, "outputs": recovered_lots, "mass_balance_method": "Residual is explicitly recorded as input minus recovered output; add notes to explain losses or reject material."}


@router.get("/processing/batches")
def get_processing_batches(db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> list[dict]:
    rows = db.scalars(select(ProcessingBatch).where(ProcessingBatch.recycler_id == user.id).order_by(ProcessingBatch.created_at.desc()).limit(100)).all()
    return [{"id": str(row.id), "process_type": row.process_type, "input_quantity_grams": row.input_quantity_grams, "recovered_quantity_grams": row.recovered_quantity_grams, "residual_quantity_grams": row.residual_quantity_grams, "notes": row.notes, "created_at": row.created_at.isoformat()} for row in rows]


@router.get("/transactions")
def get_transactions(db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> list[dict]:
    rows = db.scalars(select(MaterialTransaction).where(MaterialTransaction.recycler_id == user.id).order_by(MaterialTransaction.created_at.desc()).limit(200)).all()
    return [transaction_view(row) for row in rows]


@router.post("/transactions", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def create_sale(payload: MaterialSaleCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    lot = db.scalar(select(InventoryLot).where(InventoryLot.id == payload.lot_id, InventoryLot.recycler_id == user.id).with_for_update())
    if lot is None:
        raise HTTPException(404, "Inventory lot not found")
    balance = inventory_balance(db, lot.id)
    if payload.quantity_grams > balance:
        raise HTTPException(409, f"Sale exceeds available stock ({balance} grams)")
    amount = int((Decimal(payload.unit_price_minor_per_kg) * Decimal(payload.quantity_grams) / Decimal(1000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    transaction = MaterialTransaction(recycler_id=user.id, lot_id=lot.id, material_code=lot.category_code, quantity_grams=payload.quantity_grams, unit_price_minor_per_kg=payload.unit_price_minor_per_kg, amount_minor=amount, currency="INR", buyer_reference=payload.buyer_reference, payment_status="UNPAID")
    db.add(transaction)
    db.flush()
    db.add(InventoryLedgerEntry(lot_id=lot.id, recycler_id=user.id, quantity_delta_grams=-payload.quantity_grams, movement_type="SOLD", reason=f"Material sale transaction {transaction.id}", transaction_id=transaction.id, actor_id=user.id))
    record_audit(db, user.id, "MATERIAL_SALE_RECORDED", "material_transaction", transaction.id, {"material_code": lot.category_code, "quantity_grams": payload.quantity_grams, "amount_minor": amount, "currency": "INR"})
    db.commit()
    db.refresh(transaction)
    return transaction_view(transaction)


@router.post("/transactions/{transaction_id}/payment-confirmation", dependencies=[Depends(require_csrf)])
def confirm_payment(transaction_id: UUID, payload: PaymentConfirmIn, db: Session = Depends(get_db), user: User = Depends(require_roles("RECYCLER"))) -> dict:
    transaction = db.scalar(select(MaterialTransaction).where(MaterialTransaction.id == transaction_id, MaterialTransaction.recycler_id == user.id).with_for_update())
    if transaction is None:
        raise HTTPException(404, "Transaction not found")
    if transaction.payment_status == "PAID":
        raise HTTPException(409, "Payment is already recorded")
    previous = transaction.payment_status
    transaction.payment_status = "PAID"
    transaction.payment_reference = payload.payment_reference.strip()
    transaction.payment_confirmed_at = datetime.now(UTC)
    db.add(TransactionStatusEvent(transaction_id=transaction.id, actor_id=user.id, from_status=previous, to_status="PAID", reference=payload.payment_reference.strip()))
    record_audit(db, user.id, "PAYMENT_CONFIRMED", "material_transaction", transaction.id, {"from_status": previous, "to_status": "PAID"})
    db.commit()
    db.refresh(transaction)
    return transaction_view(transaction)
