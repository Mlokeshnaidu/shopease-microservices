"""Authentication API routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.models.user_model import User
from app.schemas.auth_schema import (
    TokenResponse,
    TokenVerifyResponse,
    ChangePassword,
    PasswordChangeResponse,
    UserLogin,
    UserRegister,
    UserRegisterResponse,
    UserResponse,
)
from app.services.auth_service import change_user_password, login_user, register_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> UserRegisterResponse:
    """Register a public user account."""
    return register_user(payload, db)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and return an access token."""
    return login_user(payload, db)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's public profile."""
    return current_user


@router.post("/verify-token", response_model=TokenVerifyResponse)
def verify_token(
    current_user: User = Depends(get_current_user),
) -> TokenVerifyResponse:
    """Verify the bearer token and return the authenticated user's profile."""
    return TokenVerifyResponse(valid=True, user=current_user)


@router.post("/change-password", response_model=PasswordChangeResponse)
def change_password(
    payload: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PasswordChangeResponse:
    """Change the authenticated user's password."""
    return change_user_password(payload, current_user, db)
