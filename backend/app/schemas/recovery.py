from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class InventoryReceiptIn(BaseModel):
    collection_id: UUID
    category_code: str = Field(min_length=2, max_length=32)
    quantity_grams: int = Field(gt=0, le=1_000_000_000)
    difference_reason: str | None = Field(default=None, max_length=500)
    location_label: str | None = Field(default=None, max_length=120)
    acquired_cost_minor: int | None = Field(default=None, ge=0, le=2_000_000_000)


class InventoryAdjustmentIn(BaseModel):
    lot_id: UUID
    quantity_delta_grams: int = Field(ge=-1_000_000_000, le=1_000_000_000)
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("quantity_delta_grams")
    @classmethod
    def nonzero_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Inventory adjustment cannot be zero")
        return value


class ProcessInputIn(BaseModel):
    lot_id: UUID
    quantity_grams: int = Field(gt=0, le=1_000_000_000)


class ProcessOutputIn(BaseModel):
    material_code: str = Field(min_length=2, max_length=32)
    quantity_grams: int = Field(gt=0, le=1_000_000_000)
    quality_grade: str | None = Field(default=None, max_length=80)


class ProcessingBatchCreate(BaseModel):
    process_type: str = Field(min_length=2, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    inputs: list[ProcessInputIn] = Field(min_length=1, max_length=30)
    outputs: list[ProcessOutputIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_batch(self):
        if len({row.lot_id for row in self.inputs}) != len(self.inputs):
            raise ValueError("Each input lot may be listed only once")
        if sum(item.quantity_grams for item in self.outputs) > sum(item.quantity_grams for item in self.inputs):
            raise ValueError("Recovered outputs cannot exceed total input mass")
        return self


class MaterialSaleCreate(BaseModel):
    lot_id: UUID
    quantity_grams: int = Field(gt=0, le=1_000_000_000)
    unit_price_minor_per_kg: int = Field(ge=0, le=100_000_000)
    buyer_reference: str | None = Field(default=None, max_length=160)


class PaymentConfirmIn(BaseModel):
    payment_reference: str = Field(min_length=3, max_length=160)
