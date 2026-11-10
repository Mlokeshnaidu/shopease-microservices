"""Pydantic schemas for user profile and account APIs."""

import re
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9()\-\s]{5,23}$")


def validate_phone(value: str) -> str:
    normalized = value.strip()
    if not _PHONE_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid phone number.")
    digits = sum(character.isdigit() for character in normalized)
    if not 7 <= digits <= 15:
        raise ValueError("Phone number must contain 7 to 15 digits.")
    return normalized


class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=150)
    phone_number: str = Field(max_length=25)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=40)
    profile_image: str | None = Field(default=None, max_length=2048)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Full name cannot be blank.")
        return cleaned

    @field_validator("phone_number")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        return validate_phone(value)

    @field_validator("gender")
    @classmethod
    def clean_gender(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    phone_number: str | None = Field(default=None, max_length=25)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=40)
    profile_image: str | None = Field(default=None, max_length=2048)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Full name cannot be blank.")
        return cleaned

    @field_validator("phone_number")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        return validate_phone(value) if value is not None else None

    @model_validator(mode="after")
    def require_non_null_required_fields(self) -> Self:
        for field in ("full_name", "phone_number"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    auth_user_id: int
    full_name: str
    phone_number: str
    date_of_birth: date | None
    gender: str | None
    profile_image: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
