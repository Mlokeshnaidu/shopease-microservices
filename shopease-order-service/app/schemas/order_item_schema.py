"""Schemas for order items."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=10000)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    product_id: int
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    discount_amount: Decimal
    total_price: Decimal
    created_at: datetime
