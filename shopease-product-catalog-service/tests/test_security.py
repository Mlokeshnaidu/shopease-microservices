from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from jose.exceptions import JWTError
import pytest

from app.core import security


def _private_key_pem(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def test_verifies_auth_service_rs256_claims(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    monkeypatch.setattr(security, "_read_public_key", lambda path: public_key)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "42",
            "role": "admin",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": security.JWT_ISSUER,
            "aud": security.JWT_AUDIENCE,
        },
        _private_key_pem(private_key),
        algorithm="RS256",
    )

    claims = security.verify_access_token(token)
    assert claims["sub"] == "42"
    assert claims["role"] == "admin"


def test_rejects_token_with_wrong_audience(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    monkeypatch.setattr(security, "_read_public_key", lambda path: public_key)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "42",
            "role": "admin",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": security.JWT_ISSUER,
            "aud": "wrong-service",
        },
        _private_key_pem(private_key),
        algorithm="RS256",
    )

    with pytest.raises(JWTError):
        security.verify_access_token(token)
