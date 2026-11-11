"""Reusable password hashing and JWT access-token helpers."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.core.config import settings

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_ISSUER = "shopease-auth-service"
JWT_AUDIENCE = "shopease-services"


@lru_cache(maxsize=4)
def _read_private_key(path: str) -> str:
    pem = Path(path).read_text(encoding="ascii")
    key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
    if not isinstance(key, RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("JWT private key must be an RSA key of at least 2048 bits.")
    return pem


@lru_cache(maxsize=4)
def _read_public_key(path: str) -> str:
    pem = Path(path).read_text(encoding="ascii")
    key = serialization.load_pem_public_key(pem.encode("ascii"))
    if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
        raise ValueError("JWT public key must be an RSA key of at least 2048 bits.")
    return pem


def load_private_key() -> str:
    return _read_private_key(str(settings.jwt_private_key_file.resolve()))


def load_public_key() -> str:
    return _read_public_key(str(settings.jwt_public_key_file.resolve()))


def validate_signing_key_pair() -> None:
    private_key = serialization.load_pem_private_key(
        load_private_key().encode("ascii"),
        password=None,
    )
    public_key = serialization.load_pem_public_key(load_public_key().encode("ascii"))
    if private_key.public_key().public_numbers() != public_key.public_numbers():
        raise ValueError("JWT private and public key files do not match.")


class InvalidAccessTokenError(ValueError):
    """Raised when an access token is malformed or fails validation."""


class ExpiredAccessTokenError(InvalidAccessTokenError):
    """Raised when an access token has expired."""


def validate_password_policy(password: str) -> None:
    """Enforce the password strength and bcrypt input-size requirements."""
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(character.isupper() for character in password):
        raise ValueError("Password must contain an uppercase letter.")
    if not any(character.islower() for character in password):
        raise ValueError("Password must contain a lowercase letter.")
    if not any(character.isdigit() for character in password):
        raise ValueError("Password must contain a digit.")


def hash_password(password: str) -> str:
    """Validate password requirements and return a bcrypt password hash."""
    validate_password_policy(password)
    return _password_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain password against its stored hash."""
    return _password_context.verify(plain_password, password_hash)


def create_access_token(user_id: str | int, role: str) -> str:
    """Create a signed access token using the configured JWT settings."""
    subject = str(user_id)
    if not subject:
        raise ValueError("User ID must not be empty.")
    if not role:
        raise ValueError("Role must not be empty.")

    issued_at = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(
        payload,
        load_private_key(),
        algorithm=settings.jwt_algorithm,
    )


def verify_access_token(token: str) -> dict[str, Any]:
    """Validate a token signature, expiry, and required access-token claims."""
    try:
        payload = jwt.decode(
            token,
            load_public_key(),
            algorithms=[settings.jwt_algorithm],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={
                "require_sub": True,
                "require_iat": True,
                "require_exp": True,
                "require_iss": True,
                "require_aud": True,
            },
        )
    except ExpiredSignatureError:
        raise ExpiredAccessTokenError("Access token has expired.") from None
    except JWTError:
        raise InvalidAccessTokenError("Access token is invalid.") from None

    if (
        not isinstance(payload.get("sub"), str)
        or not payload["sub"]
        or not isinstance(payload.get("role"), str)
        or not payload["role"]
        or not isinstance(payload.get("iat"), int)
        or not isinstance(payload.get("exp"), int)
    ):
        raise InvalidAccessTokenError("Access token is invalid.")

    return payload
