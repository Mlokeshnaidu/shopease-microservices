"""Schemas for customer orders."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.order_item_schema import OrderItemCreate, OrderItemRead


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemCreate] = Field(min_length=1, max_length=100)
    shipping_address_id: int = Field(gt=0)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_status: str | None = None
    payment_status: str | None = None

    @model_validator(mode="after")
    def require_a_status(self) -> "OrderStatusUpdate":
        if self.order_status is None and self.payment_status is None:
            raise ValueError("At least one status field must be provided.")
        return self

    @field_validator("order_status")
    @classmethod
    def validate_order_status(cls, value: str | None) -> str | None:
        allowed = {
            "PENDING",
            "CONFIRMED",
            "PROCESSING",
            "SHIPPED",
            "DELIVERED",
            "CANCELLED",
        }
        if value is not None:
            value = value.strip().upper()
            if value not in allowed:
                raise ValueError(f"order_status must be one of {', '.join(sorted(allowed))}.")
        return value

    @field_validator("payment_status")
    @classmethod
    def validate_payment_status(cls, value: str | None) -> str | None:
        allowed = {"PENDING", "PAID", "FAILED", "REFUNDED"}
        if value is not None:
            value = value.strip().upper()
            if value not in allowed:
                raise ValueError(f"payment_status must be one of {', '.join(sorted(allowed))}.")
        return value


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str
    user_id: int
    shipping_address: dict
    subtotal: Decimal
    discount_amount: Decimal
    shipping_charge: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    order_status: str
    payment_status: str
    inventory_status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class OrderListRead(BaseModel):
    items: list[OrderRead]
    total: int
    page: int
    page_size: int
