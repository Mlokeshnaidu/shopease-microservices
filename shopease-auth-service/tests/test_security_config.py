import pytest
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.security import hash_password, validate_password_policy
from app.schemas.auth_schema import UserRegister
from app.services.auth_service import register_user


def make_settings(**overrides) -> Settings:
    values = {
        "mysql_database": "test_db",
        "mysql_user": "test_user",
        "mysql_password": "mysql-test-password",
        "jwt_secret_key": "a" * 64,
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


@pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
def test_jwt_settings_accept_allowed_algorithms_with_sufficient_key(algorithm):
    required_bytes = {"HS256": 32, "HS384": 48, "HS512": 64}[algorithm]
    configured = make_settings(
        jwt_algorithm=algorithm,
        jwt_secret_key="s" * required_bytes,
    )

    assert configured.jwt_algorithm == algorithm


def test_jwt_settings_reject_unknown_algorithm():
    with pytest.raises(ValidationError, match="JWT_ALGORITHM"):
        make_settings(jwt_algorithm="none")


@pytest.mark.parametrize(
    ("algorithm", "secret"),
    [
        ("HS256", "s" * 31),
        ("HS384", "s" * 47),
        ("HS512", "s" * 63),
    ],
)
def test_jwt_settings_reject_weak_secret(algorithm, secret):
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        make_settings(jwt_algorithm=algorithm, jwt_secret_key=secret)


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
