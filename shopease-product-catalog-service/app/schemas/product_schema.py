"""Pydantic schemas for catalog product requests and responses."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class ProductCreate(BaseModel):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10000)
    sku: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    discount_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock_quantity: int = Field(default=0, ge=0)
    image_url: HttpUrl | None = None
    brand: str | None = Field(default=None, max_length=100)
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "sku", "brand", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Value must be text.")
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank.")
        return value

    @model_validator(mode="after")
    def discount_cannot_exceed_price(self) -> "ProductCreate":
        if self.discount_price is not None and self.discount_price > self.price:
            raise ValueError("Discount price cannot exceed product price.")
        return self


class ProductUpdate(BaseModel):
    category_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=10000)
    sku: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    discount_price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock_quantity: int | None = Field(default=None, ge=0)
    image_url: HttpUrl | None = None
    brand: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("category_id", "name", "sku", "price", "stock_quantity", mode="before")
    @classmethod
    def required_when_supplied(cls, value: int | str | Decimal) -> int | str | Decimal:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value

    @field_validator("name", "sku", "brand", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Value must be text.")
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_discount(self) -> "ProductUpdate":
        if self.discount_price is not None and self.price is not None and self.discount_price > self.price:
            raise ValueError("Discount price cannot exceed product price.")
        return self


class ProductResponse(BaseModel):
    id: int
    category_id: int
    name: str
    description: str | None
    sku: str
    price: Decimal
    discount_price: Decimal | None
    stock_quantity: int
    image_url: str | None
    brand: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductDetailResponse(ProductResponse):
    category: "CategorySummary"


class CategorySummary(BaseModel):
    id: int
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
