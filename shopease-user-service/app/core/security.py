"""JWT access-token verification compatible with the Authentication Service."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from jose import JWTError, jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.core.config import settings

JWT_ISSUER = "shopease-auth-service"
JWT_AUDIENCE = "shopease-services"


@lru_cache(maxsize=4)
def _read_public_key(path: str) -> str:
    pem = Path(path).read_text(encoding="ascii")
    key = serialization.load_pem_public_key(pem.encode("ascii"))
    if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
        raise ValueError("JWT public key must be an RSA key of at least 2048 bits.")
    return pem


def load_public_key() -> str:
    return _read_public_key(str(settings.jwt_public_key_file.resolve()))


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
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
    except JWTError:
        raise ValueError("Access token is invalid or expired.") from None

    if (
        not isinstance(claims.get("sub"), str)
        or not claims["sub"]
        or not isinstance(claims.get("role"), str)
        or not claims["role"]
        or not isinstance(claims.get("iat"), int)
        or not isinstance(claims.get("exp"), int)
    ):
        raise ValueError("Access token is invalid or expired.")
    return claims
