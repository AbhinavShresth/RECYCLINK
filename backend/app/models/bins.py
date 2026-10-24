from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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


class SmartBin(Base):
    __tablename__ = "smart_bins"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_bin_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_bin_longitude"),
        CheckConstraint("capacity_grams > 0", name="ck_bin_capacity_positive"),
        CheckConstraint("fill_percent >= 0 AND fill_percent <= 100", name="ck_bin_fill_range"),
        CheckConstraint("battery_percent IS NULL OR (battery_percent >= 0 AND battery_percent <= 100)", name="ck_bin_battery_range"),
        CheckConstraint("connectivity_status IN ('ONLINE','OFFLINE')", name="ck_bin_connectivity"),
        CheckConstraint("sensor_source IN ('SIMULATED','DEVICE')", name="ck_bin_sensor_source"),
        UniqueConstraint("bin_code", name="uq_smart_bin_code"),
        Index("ix_bins_category_status", "category_code", "operational_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    bin_code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    category_code: Mapped[str] = mapped_column(ForeignKey("waste_categories.code", ondelete="RESTRICT"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    fill_percent: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    battery_percent: Mapped[float | None] = mapped_column(Float)
    connectivity_status: Mapped[str] = mapped_column(String(10), default="ONLINE", nullable=False)
    operational_status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    sensor_source: Mapped[str] = mapped_column(String(12), default="SIMULATED", nullable=False)
    service_area: Mapped[str | None] = mapped_column(String(120))
    last_reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class BinSensorReading(Base):
    __tablename__ = "bin_sensor_readings"
    __table_args__ = (
        CheckConstraint("fill_percent >= 0 AND fill_percent <= 100", name="ck_bin_reading_fill_range"),
        CheckConstraint("battery_percent IS NULL OR (battery_percent >= 0 AND battery_percent <= 100)", name="ck_bin_reading_battery_range"),
        Index("ix_bin_readings_bin_time", "bin_id", "reported_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    bin_id: Mapped[UUID] = mapped_column(ForeignKey("smart_bins.id", ondelete="CASCADE"), nullable=False)
    fill_percent: Mapped[float] = mapped_column(Float, nullable=False)
    battery_percent: Mapped[float | None] = mapped_column(Float)
    connectivity_status: Mapped[str] = mapped_column(String(10), nullable=False)
    sensor_source: Mapped[str] = mapped_column(String(12), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BinAlert(Base):
    __tablename__ = "bin_alerts"
    __table_args__ = (Index("ix_bin_alerts_open_created", "is_open", "created_at"), Index("ix_bin_alerts_bin_open", "bin_id", "is_open"))
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    bin_id: Mapped[UUID] = mapped_column(ForeignKey("smart_bins.id", ondelete="CASCADE"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reported_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BinCollectionEvent(Base):
    __tablename__ = "bin_collection_events"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    bin_id: Mapped[UUID] = mapped_column(ForeignKey("smart_bins.id", ondelete="CASCADE"), nullable=False, index=True)
    collected_quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
