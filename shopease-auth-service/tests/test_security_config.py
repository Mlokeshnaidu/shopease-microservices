import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, settings
from app.core.security import (
    hash_password,
    validate_password_policy,
    validate_signing_key_pair,
)
from app.schemas.auth_schema import UserRegister
from app.services.auth_service import register_user


def make_settings(**overrides) -> Settings:
    values = {
        "mysql_database": "test_db",
        "mysql_user": "test_user",
        "mysql_password": "mysql-test-password",
        "jwt_private_key_file": os.environ["JWT_PRIVATE_KEY_FILE"],
        "jwt_public_key_file": os.environ["JWT_PUBLIC_KEY_FILE"],
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_bcrypt_accepts_password_exactly_72_utf8_bytes():
    password = "A1" + ("a" * 68) + "é"
    assert len(password.encode("utf-8")) == 72

    validate_password_policy(password)
    assert hash_password(password)


def test_bcrypt_rejects_password_over_72_utf8_bytes_without_truncating():
    password = "A1" + ("a" * 68) + "éx"
    assert len(password.encode("utf-8")) == 73

    with pytest.raises(ValueError, match="72 UTF-8 bytes"):
        hash_password(password)

    with pytest.raises(ValidationError):
        UserRegister(
            full_name="Test User",
            email="test@example.com",
            password=password,
            confirm_password=password,
        )


def test_jwt_settings_require_rs256():
    assert make_settings().jwt_algorithm == "RS256"


def test_startup_rejects_mismatched_signing_key_pair(tmp_path, monkeypatch):
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key_path = tmp_path / "other_public.pem"
    public_key_path.write_bytes(
        other_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    monkeypatch.setattr(settings, "jwt_public_key_file", public_key_path)

    with pytest.raises(ValueError, match="do not match"):
        validate_signing_key_pair()


@pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512", "none"])
def test_jwt_settings_reject_non_rs256_algorithm(algorithm):
    with pytest.raises(ValidationError, match="JWT_ALGORITHM"):
        make_settings(jwt_algorithm=algorithm)


@pytest.mark.parametrize("expiry", [0, -1])
def test_jwt_settings_reject_nonpositive_expiry(expiry):
    with pytest.raises(ValidationError, match="ACCESS_TOKEN_EXPIRE_MINUTES"):
        make_settings(access_token_expire_minutes=expiry)


def test_registration_database_lookup_error_returns_generic_503(caplog):
    class BrokenDatabase:
        def scalar(self, statement):
            raise OperationalError(
                "SELECT users",
                {},
                RuntimeError("database-credential-must-not-be-logged"),
            )

    payload = UserRegister(
        full_name="Test User",
        email="test@example.com",
        password=SecretStr("StrongPass9"),
        confirm_password=SecretStr("StrongPass9"),
    )

    with pytest.raises(HTTPException) as raised:
        register_user(payload, BrokenDatabase())

    assert raised.value.status_code == 503
    assert raised.value.detail == "Account registration is temporarily unavailable."
    assert "database-credential-must-not-be-logged" not in caplog.text
