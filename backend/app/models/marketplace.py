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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class WasteListing(Base):
    __tablename__ = "waste_listings"
    __table_args__ = (
        CheckConstraint("quantity_grams > 0", name="ck_listing_quantity_positive"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_listing_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_listing_longitude"),
        CheckConstraint("status IN ('OPEN','ACCEPTED','CANCELLED','CLOSED')", name="ck_listing_status"),
        Index("ix_listing_status_created", "status", "created_at"),
        Index("ix_listing_category_status", "category_code", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    classification_id: Mapped[UUID | None] = mapped_column(ForeignKey("waste_classifications.id", ondelete="SET NULL"))
    category_code: Mapped[str] = mapped_column(ForeignKey("waste_categories.code", ondelete="RESTRICT"), nullable=False)
    quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(String(1200))
    pickup_address: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    preferred_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferred_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class RecyclerOffer(Base):
    __tablename__ = "recycler_offers"
    __table_args__ = (
        CheckConstraint("price_minor_per_kg >= 0", name="ck_offer_price_nonnegative"),
        CheckConstraint("pickup_fee_minor >= 0", name="ck_offer_fee_nonnegative"),
        CheckConstraint("status IN ('SUBMITTED','ACCEPTED','REJECTED','WITHDRAWN','EXPIRED')", name="ck_offer_status"),
        UniqueConstraint("listing_id", "recycler_id", name="uq_offer_listing_recycler"),
        Index("ix_offer_listing_status", "listing_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("waste_listings.id", ondelete="CASCADE"), nullable=False)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), nullable=False, index=True)
    price_minor_per_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    pickup_fee_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    proposed_pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(600))
    status: Mapped[str] = mapped_column(String(16), default="SUBMITTED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class CollectionRequest(Base):
    __tablename__ = "collection_requests"
    __table_args__ = (
        CheckConstraint("estimated_quantity_grams > 0", name="ck_collection_estimated_positive"),
        CheckConstraint("actual_quantity_grams IS NULL OR actual_quantity_grams >= 0", name="ck_collection_actual_nonnegative"),
        CheckConstraint("status IN ('ACCEPTED','SCHEDULED','ASSIGNED','EN_ROUTE','ARRIVED','COLLECTED','WEIGHED','PROCESSING','COMPLETED','CANCELLED','DISPUTED')", name="ck_collection_status"),
        UniqueConstraint("listing_id", name="uq_collection_listing"),
        UniqueConstraint("offer_id", name="uq_collection_offer"),
        Index("ix_collection_user_status", "user_id", "status"),
        Index("ix_collection_recycler_status", "recycler_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    listing_id: Mapped[UUID] = mapped_column(ForeignKey("waste_listings.id", ondelete="RESTRICT"), nullable=False)
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_offers.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), nullable=False)
    estimated_quantity_grams: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_quantity_grams: Mapped[int | None] = mapped_column(Integer)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ACCEPTED", nullable=False)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class CollectionStatusHistory(Base):
    __tablename__ = "collection_status_history"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collection_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_created", "user_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    collection_id: Mapped[UUID | None] = mapped_column(ForeignKey("collection_requests.id", ondelete="CASCADE"))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RoutePlan(Base):
    __tablename__ = "route_plans"
    __table_args__ = (Index("ix_route_plans_recycler_created", "recycler_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), nullable=False)
    start_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    start_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    end_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    end_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_distance_meters: Mapped[float] = mapped_column(nullable=False)
    optimized_distance_meters: Mapped[float] = mapped_column(nullable=False)
    baseline_duration_seconds: Mapped[float] = mapped_column(nullable=False)
    optimized_duration_seconds: Mapped[float] = mapped_column(nullable=False)
    distance_saved_percentage: Mapped[float | None] = mapped_column()
    duration_saved_percentage: Mapped[float | None] = mapped_column()
    geometry_json: Mapped[str] = mapped_column(Text, nullable=False)
    router_data_version: Mapped[str | None] = mapped_column(String(80))
    method: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = (UniqueConstraint("route_id", "sequence", name="uq_route_stop_sequence"), UniqueConstraint("route_id", "collection_id", name="uq_route_stop_collection"))
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    route_id: Mapped[UUID] = mapped_column(ForeignKey("route_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id: Mapped[UUID] = mapped_column(ForeignKey("collection_requests.id", ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
