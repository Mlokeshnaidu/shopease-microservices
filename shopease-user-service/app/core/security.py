"""JWT access-token verification compatible with the Authentication Service."""

from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require_sub": True, "require_iat": True, "require_exp": True},
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
