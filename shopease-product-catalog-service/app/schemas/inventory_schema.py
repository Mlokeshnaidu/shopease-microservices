"""Pydantic schemas for inventory operations and transaction history."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StockAdjustment(BaseModel):
    quantity: int = Field(gt=0)
    remarks: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class InventoryResponse(BaseModel):
    product_id: int
    sku: str
    name: str
    stock_quantity: int
    available: bool


class InventoryTransactionResponse(BaseModel):
    id: int
    product_id: int
    transaction_type: str
    quantity: int
    previous_stock: int
    updated_stock: int
    remarks: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
