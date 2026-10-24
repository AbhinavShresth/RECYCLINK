from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceAreaIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    radius_meters: int = Field(default=25_000, ge=100, le=500_000)


class AcceptedCategoryIn(BaseModel):
    category_code: str = Field(min_length=1, max_length=32)
    indicative_price_minor_per_kg: int | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern="^[A-Z]{3}$")


class RecyclerProfileIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    phone_public: str | None = Field(default=None, max_length=32)
    min_pickup_grams: int = Field(default=0, ge=0)
    max_capacity_grams: int | None = Field(default=None, gt=0)
    service_areas: list[ServiceAreaIn] = Field(min_length=1, max_length=20)
    accepted_categories: list[AcceptedCategoryIn] = Field(min_length=1, max_length=8)


class ServiceAreaOut(ServiceAreaIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class AcceptedCategoryOut(AcceptedCategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class RecyclerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    business_name: str
    description: str | None
    phone_public: str | None
    min_pickup_grams: int
    max_capacity_grams: int | None
    verified_at: datetime | None
    service_areas: list[ServiceAreaOut]
    accepted_categories: list[AcceptedCategoryOut]
