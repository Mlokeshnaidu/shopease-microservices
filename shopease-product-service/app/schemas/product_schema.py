from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ProductStatus(str, Enum):
    """Predefined product status values."""
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class ProductBase(BaseModel):
    """Base Pydantic model for common product fields."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the product. Must be between 1 and 100 characters and contain meaningful text.",
        examples=["Wireless Noise-Canceling Headphones"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional detailed description of the product, up to 1000 characters.",
        examples=["Premium over-ear Bluetooth headphones with 30-hour battery life."]
    )
    price: float = Field(
        ...,
        gt=0,
        description="Price of the product. Must be strictly greater than 0.",
        examples=[149.99]
    )
    stock_quantity: int = Field(
        ...,
        ge=0,
        description="Available inventory count. Must be a non-negative integer (>= 0).",
        examples=[50]
    )
    category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Category to which the product belongs.",
        examples=["Electronics"]
    )
    status: ProductStatus = Field(
        default=ProductStatus.ACTIVE,
        description="Operational status of the product: 'Active' or 'Inactive'.",
        examples=[ProductStatus.ACTIVE]
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("Product Name must not be empty or contain only whitespace.")
            return trimmed
        raise ValueError("Product Name must be a string.")

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, value: str) -> str:
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                raise ValueError("Product Category must not be empty or contain only whitespace.")
            return trimmed
        raise ValueError("Product Category must be a string.")


class ProductCreate(ProductBase):
    """Schema for creating a new product."""
    pass


class ProductUpdate(ProductBase):
    """Schema for updating an existing product."""
    pass


class ProductResponse(BaseModel):
    """Schema for product responses returned to clients."""
    product_id: str = Field(..., description="Unique product identifier", examples=["PROD-A1B2C3D4"])
    name: str = Field(..., description="Name of the product")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., description="Product price")
    stock_quantity: int = Field(..., description="Current stock level")
    category: str = Field(..., description="Product category")
    status: ProductStatus = Field(..., description="Product status")
    created_at: datetime = Field(..., description="Timestamp when the product was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the product was last updated")

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Standard generic message response schema."""
    message: str = Field(..., description="Status or confirmation message")

