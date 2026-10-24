from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class CoordinateIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ListingCreate(BaseModel):
    category_code: str = Field(min_length=2, max_length=32)
    quantity_grams: int = Field(gt=0, le=1_000_000_000)
    condition: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=1200)
    pickup_address: str = Field(min_length=5, max_length=500)
    location: CoordinateIn
    classification_id: UUID | None = None
    preferred_start: datetime | None = None
    preferred_end: datetime | None = None

    @field_validator("pickup_address")
    @classmethod
    def clean_address(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def valid_window(self):
        if self.preferred_start and self.preferred_end and self.preferred_end <= self.preferred_start:
            raise ValueError("Pickup window end must be after its start")
        return self


class OfferCreate(BaseModel):
    price_minor_per_kg: int = Field(ge=0, le=100_000_000)
    pickup_fee_minor: int = Field(default=0, ge=0, le=100_000_000)
    proposed_pickup_at: datetime | None = None
    expires_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=600)

    @model_validator(mode="after")
    def valid_expiry(self):
        if self.expires_at and self.expires_at <= datetime.now(self.expires_at.tzinfo):
            raise ValueError("Offer expiry must be in the future")
        return self


class TransitionIn(BaseModel):
    status: str = Field(min_length=3, max_length=20)
    reason: str | None = Field(default=None, max_length=500)
    actual_quantity_grams: int | None = Field(default=None, ge=0, le=1_000_000_000)
    scheduled_at: datetime | None = None


class ListingPublic(BaseModel):
    id: UUID
    owner_id: UUID
    category_code: str
    quantity_grams: int
    condition: str | None
    description: str | None
    status: str
    created_at: datetime
    offer_count: int
    pickup_address: str | None = None
