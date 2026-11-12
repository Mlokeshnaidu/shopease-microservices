"""JWT authentication and role dependencies."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import verify_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def require_admin(claims: Annotated[dict[str, Any], Depends(get_current_claims)]) -> dict[str, Any]:
    if claims["role"].strip().lower() not in {"admin", "administrator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    return claims


CurrentClaims = Annotated[dict[str, Any], Depends(get_current_claims)]
AdminClaims = Annotated[dict[str, Any], Depends(require_admin)]
