"""Pydantic v2 schemas for authentication requests and responses."""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.core.security import validate_password_policy


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserRegister(_StrictRequest):
    """Public registration input; role and active status are not client-settable."""

    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: SecretStr
    confirm_password: SecretStr

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Full name must not be blank.")
        return value

    @field_validator("password", "confirm_password")
    @classmethod
    def validate_password_strength(cls, value: SecretStr) -> SecretStr:
        validate_password_policy(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "UserRegister":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirmation do not match.")
        return self


class UserRegisterResponse(BaseModel):
    """Fields returned after public registration."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    message: str = "Registration successful."
    id: int
    full_name: str
    email: EmailStr
    is_active: bool


class UserLogin(_StrictRequest):
    """User login credentials."""

    email: EmailStr
    password: SecretStr


class UserResponse(BaseModel):
    """Public user data; sensitive credential fields are intentionally omitted."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: int
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Access token and the public user profile returned at authentication."""

    message: str = "Login successful."
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePassword(_StrictRequest):
    """Current password and validated replacement password."""

    current_password: SecretStr
    new_password: SecretStr
    confirm_new_password: SecretStr

    @field_validator("new_password", "confirm_new_password")
    @classmethod
    def validate_password_strength(cls, value: SecretStr) -> SecretStr:
        validate_password_policy(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def new_passwords_match(self) -> "ChangePassword":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New password and confirmation do not match.")
        return self


class PasswordChangeResponse(BaseModel):
    """Confirmation returned after a password change."""

    message: str


class TokenVerifyResponse(BaseModel):
    """Token verification result and, when valid, the public user profile."""

    valid: bool
    user: UserResponse | None = None
