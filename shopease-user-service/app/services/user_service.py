"""Business logic for customer profiles and local account status."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user_model import UserProfile
from app.schemas.user_schema import ProfileCreate, ProfileUpdate


def get_active_profile(db: Session, auth_user_id: int) -> UserProfile:
    profile = db.scalar(
        select(UserProfile).where(
            UserProfile.auth_user_id == auth_user_id,
            UserProfile.is_active.is_(True),
        )
    )
    if profile is None:
        existing = db.scalar(
            select(UserProfile.id).where(UserProfile.auth_user_id == auth_user_id)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This user profile is deactivated.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )
    return profile


def create_profile(db: Session, auth_user_id: int, data: ProfileCreate) -> UserProfile:
    if db.scalar(
        select(UserProfile.id).where(UserProfile.auth_user_id == auth_user_id)
    ) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile already exists for this account.",
        )
    profile = UserProfile(auth_user_id=auth_user_id, **data.model_dump())
    try:
        db.add(profile)
        db.commit()
        db.refresh(profile)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile already exists for this account.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to save profile at this time.",
        ) from exc
    return profile


def update_profile(
    db: Session, auth_user_id: int, data: ProfileUpdate
) -> UserProfile:
    profile = get_active_profile(db, auth_user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    try:
        db.commit()
        db.refresh(profile)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to update profile at this time.",
        ) from exc
    return profile


def delete_profile(db: Session, auth_user_id: int) -> None:
    profile = get_active_profile(db, auth_user_id)
    try:
        db.delete(profile)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to delete profile at this time.",
        ) from exc


def deactivate_profile(db: Session, auth_user_id: int) -> UserProfile:
    profile = get_active_profile(db, auth_user_id)
    profile.is_active = False
    profile.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
        db.refresh(profile)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to deactivate profile at this time.",
        ) from exc
    return profile
