"""Request dependencies for JWT authentication and role checks."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import verify_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def get_authenticated_claims(
    token: Annotated[str, Depends(get_auth_token)],
) -> dict:
    try:
        claims = verify_access_token(token)
    except (JWTError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return claims


def get_current_user_id(
    claims: Annotated[dict, Depends(get_authenticated_claims)],
) -> int:
    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    if user_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


def require_admin(
    claims: Annotated[dict, Depends(get_authenticated_claims)],
) -> dict:
    if str(claims.get("role", "")).strip().lower() not in {"admin", "administrator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return claims
