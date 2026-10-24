from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    profile: Mapped["UserProfile"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    locations: Mapped[list["UserLocation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    recycler_profile: Mapped["RecyclerProfile | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)


class Role(Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    description: Mapped[str] = mapped_column(String(180), nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_code", name="uq_user_role"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code", ondelete="RESTRICT"), index=True)
    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user: Mapped[User] = relationship(back_populates="profile")


class UserLocation(Base):
    __tablename__ = "user_locations"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_location_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_location_longitude"),
        Index("ix_user_locations_owner_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    user: Mapped[User] = relationship(back_populates="locations")


class WasteCategory(Base):
    __tablename__ = "waste_categories"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RecyclerProfile(Base):
    __tablename__ = "recycler_profiles"
    __table_args__ = (
        CheckConstraint("min_pickup_grams >= 0", name="ck_recycler_min_pickup_nonnegative"),
        CheckConstraint("max_capacity_grams IS NULL OR max_capacity_grams > 0", name="ck_recycler_capacity_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    business_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    phone_public: Mapped[str | None] = mapped_column(String(32))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    min_pickup_grams: Mapped[int] = mapped_column(default=0, nullable=False)
    max_capacity_grams: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    user: Mapped[User] = relationship(back_populates="recycler_profile")
    service_areas: Mapped[list["RecyclerServiceArea"]] = relationship(back_populates="recycler", cascade="all, delete-orphan")
    accepted_categories: Mapped[list["RecyclerAcceptedCategory"]] = relationship(back_populates="recycler", cascade="all, delete-orphan")


class RecyclerServiceArea(Base):
    __tablename__ = "recycler_service_areas"
    __table_args__ = (
        CheckConstraint("center_latitude >= -90 AND center_latitude <= 90", name="ck_service_area_latitude"),
        CheckConstraint("center_longitude >= -180 AND center_longitude <= 180", name="ck_service_area_longitude"),
        CheckConstraint("radius_meters >= 100 AND radius_meters <= 500000", name="ck_service_area_radius"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    center_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    center_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[int] = mapped_column(default=25000, nullable=False)
    recycler: Mapped[RecyclerProfile] = relationship(back_populates="service_areas")


class RecyclerAcceptedCategory(Base):
    __tablename__ = "recycler_accepted_categories"
    __table_args__ = (
        UniqueConstraint("recycler_id", "category_code", name="uq_recycler_category"),
        CheckConstraint("indicative_price_minor_per_kg IS NULL OR indicative_price_minor_per_kg >= 0", name="ck_price_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    recycler_id: Mapped[UUID] = mapped_column(ForeignKey("recycler_profiles.user_id", ondelete="CASCADE"), index=True)
    category_code: Mapped[str] = mapped_column(ForeignKey("waste_categories.code", ondelete="RESTRICT"), index=True)
    indicative_price_minor_per_kg: Mapped[int | None] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    recycler: Mapped[RecyclerProfile] = relationship(back_populates="accepted_categories")
