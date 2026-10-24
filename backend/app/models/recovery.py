from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class InventoryLot(Base):
    __tablename__ = "inventory_lots"
    __table_args__ = (
        CheckConstraint("initial_quantity_grams > 0", name="ck_inventory_lot_quantity_positive"),
        Index("ix_inventory_lots_recycler_category", "recycler_id", "category_code"),
        UniqueConstraint("origin_collection_id", name="uq_inventory_origin_collection"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), nullable=False)
    category_code: Mapped[str] = mapped_column(ForeignKey("waste_categories.code", ondelete="RESTRICT"), nullable=False)
    origin_collection_id: Mapped[UUID | None] = mapped_column(ForeignKey("collection_requests.id", ondelete="RESTRICT"))
    source_batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("processing_batches.id", ondelete="RESTRICT"))
    initial_quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    location_label: Mapped[str | None] = mapped_column(String(120))
    acquired_cost_minor: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class InventoryLedgerEntry(Base):
    __tablename__ = "inventory_ledger_entries"
    __table_args__ = (
        CheckConstraint("quantity_delta_grams <> 0", name="ck_inventory_movement_nonzero"),
        Index("ix_inventory_ledger_lot_created", "lot_id", "created_at"),
        Index("ix_inventory_ledger_recycler_created", "recycler_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=False)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), nullable=False)
    quantity_delta_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    collection_id: Mapped[UUID | None] = mapped_column(ForeignKey("collection_requests.id", ondelete="RESTRICT"))
    processing_batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("processing_batches.id", ondelete="RESTRICT"))
    transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("material_transactions.id", ondelete="RESTRICT"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProcessingBatch(Base):
    __tablename__ = "processing_batches"
    __table_args__ = (Index("ix_processing_recycler_created", "recycler_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), nullable=False)
    process_type: Mapped[str] = mapped_column(String(120), nullable=False)
    input_quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    recovered_quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProcessingInput(Base):
    __tablename__ = "processing_inputs"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("processing_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=False)
    quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)


class RecoveredMaterial(Base):
    __tablename__ = "recovered_materials"
    __table_args__ = (CheckConstraint("quantity_grams > 0", name="ck_recovered_quantity_positive"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(ForeignKey("processing_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=False)
    material_code: Mapped[str] = mapped_column(ForeignKey("waste_categories.code", ondelete="RESTRICT"), nullable=False)
    quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_grade: Mapped[str | None] = mapped_column(String(80))


class MaterialTransaction(Base):
    __tablename__ = "material_transactions"
    __table_args__ = (
        CheckConstraint("quantity_grams > 0", name="ck_transaction_quantity_positive"),
        CheckConstraint("unit_price_minor_per_kg >= 0 AND amount_minor >= 0", name="ck_transaction_money_nonnegative"),
        CheckConstraint("payment_status IN ('UNPAID','PAID')", name="ck_transaction_payment_status"),
        Index("ix_transactions_recycler_created", "recycler_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), nullable=False)
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_lots.id", ondelete="RESTRICT"), nullable=False)
    material_code: Mapped[str] = mapped_column(ForeignKey("waste_categories.code", ondelete="RESTRICT"), nullable=False)
    quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_minor_per_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    buyer_reference: Mapped[str | None] = mapped_column(String(160))
    payment_status: Mapped[str] = mapped_column(String(10), default="UNPAID", nullable=False)
    payment_reference: Mapped[str | None] = mapped_column(String(160))
    payment_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TransactionStatusEvent(Base):
    __tablename__ = "transaction_status_events"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("material_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    from_status: Mapped[str] = mapped_column(String(10), nullable=False)
    to_status: Mapped[str] = mapped_column(String(10), nullable=False)
    reference: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
