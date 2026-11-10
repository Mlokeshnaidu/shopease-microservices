"""Request dependencies for JWT authentication."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> int:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        claims = verify_access_token(credentials.credentials)
        user_id = int(claims["sub"])
    except (ValueError, KeyError, TypeError):
        raise unauthorized from None
    if user_id <= 0:
        raise unauthorized
    return user_id
