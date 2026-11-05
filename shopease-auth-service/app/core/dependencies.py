"""Reusable authentication dependencies for protected API routes."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import InvalidAccessTokenError, verify_access_token
from app.database.connection import get_db
from app.models.user_model import User

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Validate a bearer token and return its active database user."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_error

    try:
        claims = verify_access_token(credentials.credentials)
    except InvalidAccessTokenError:
        raise credentials_error from None

    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        raise credentials_error from None

    token_role = claims.get("role")
    if user_id <= 0 or not isinstance(token_role, str) or not token_role:
        raise credentials_error

    try:
        user = db.scalar(select(User).where(User.id == user_id))
    except SQLAlchemyError as exc:
        logger.error("Unable to retrieve the authenticated account.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        ) from exc

    if user is None or not user.is_active or user.role != token_role:
        raise credentials_error

    return user
