"""Pydantic schemas for delivery address APIs."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.user_schema import validate_phone


class AddressFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address_type: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=150)
    phone_number: str = Field(max_length=25)
    address_line_1: str = Field(min_length=1, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)

    @field_validator(
        "address_type", "full_name", "address_line_1", "city", "state", "country", "postal_code"
    )
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be blank.")
        return cleaned

    @field_validator("phone_number")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        return validate_phone(value)

    @field_validator("address_line_2")
    @classmethod
    def clean_optional_address(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class AddressCreate(AddressFields):
    is_default: bool = False


class AddressUpdate(AddressFields):
    is_default: bool = False


class AddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    address_type: str
    full_name: str
    phone_number: str
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    country: str
    postal_code: str
    is_default: bool
    created_at: datetime
