"""Business logic for authentication operations."""

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user_model import User
from app.schemas.auth_schema import ChangePassword, TokenResponse, UserLogin, UserRegister

logger = logging.getLogger(__name__)


def register_user(payload: UserRegister, db: Session) -> User:
    """Create a user account, rejecting duplicate email addresses."""
    try:
        existing_user = db.scalar(select(User).where(User.email == str(payload.email)))
    except SQLAlchemyError as exc:
        logger.error("Unable to check an authentication account.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account registration is temporarily unavailable.",
        ) from exc

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        email=str(payload.email),
        password_hash=hash_password(payload.password.get_secret_value()),
        role="user",
        is_active=True,
    )
    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Unable to create an authentication account.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account registration is temporarily unavailable.",
        ) from exc

    return user


def login_user(payload: UserLogin, db: Session) -> TokenResponse:
    """Authenticate an active user and return an access token."""
    try:
        user = db.scalar(select(User).where(User.email == str(payload.email)))
    except SQLAlchemyError as exc:
        logger.error("Unable to look up an authentication account.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login is temporarily unavailable.",
        ) from exc

    if user is None or not verify_password(
        payload.password.get_secret_value(),
        user.password_hash if user is not None else "",
    ) or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        access_token = create_access_token(user_id=user.id, role=user.role)
    except ValueError as exc:
        logger.error("Unable to issue an authentication token.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login is temporarily unavailable.",
        ) from exc

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user,
    )


def change_user_password(
    payload: ChangePassword,
    user: User,
    db: Session,
) -> dict[str, str]:
    """Verify and update the password for an authenticated user."""
    current_password = payload.current_password.get_secret_value()
    new_password = payload.new_password.get_secret_value()

    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if verify_password(new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password.",
        )

    user.password_hash = hash_password(new_password)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Unable to update an authentication password.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password change is temporarily unavailable.",
        ) from exc

    return {"message": "Password changed successfully."}
