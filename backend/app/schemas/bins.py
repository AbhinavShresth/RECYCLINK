from uuid import UUID

from pydantic import BaseModel, Field


class BinCreate(BaseModel):
    bin_code: str = Field(min_length=2, max_length=40, pattern="^[A-Za-z0-9_-]+$")
    label: str = Field(min_length=2, max_length=160)
    category_code: str = Field(min_length=2, max_length=32)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    capacity_grams: int = Field(gt=0, le=1_000_000_000)
    fill_percent: float = Field(default=0, ge=0, le=100)
    battery_percent: float | None = Field(default=100, ge=0, le=100)
    service_area: str | None = Field(default=None, max_length=120)


class BinReadingIn(BaseModel):
    fill_percent: float = Field(ge=0, le=100)
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    connectivity_status: str = Field(default="ONLINE", pattern="^(ONLINE|OFFLINE)$")


class SimulatorTickIn(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    fill_increment_min: float = Field(default=1, ge=0, le=20)
    fill_increment_max: float = Field(default=7, ge=0, le=30)
    offline_probability: float = Field(default=0.04, ge=0, le=1)


class BinCollectionIn(BaseModel):
    collected_quantity_grams: int = Field(gt=0, le=1_000_000_000)
    notes: str | None = Field(default=None, max_length=500)


class BinIdIn(BaseModel):
    bin_id: UUID
