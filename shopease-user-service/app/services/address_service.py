"""Business logic for addresses, always scoped to the owning profile."""

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.address_model import Address
from app.models.user_model import UserProfile
from app.schemas.address_schema import AddressCreate, AddressUpdate
from app.services.user_service import get_active_profile


def _lock_profile(db: Session, auth_user_id: int) -> UserProfile:
    profile = db.scalar(
        select(UserProfile)
        .where(
            UserProfile.auth_user_id == auth_user_id,
            UserProfile.is_active.is_(True),
        )
        .with_for_update()
    )
    if profile is None:
        return get_active_profile(db, auth_user_id)
    return profile


def _owned_address(db: Session, user_id: int, address_id: int) -> Address:
    address = db.scalar(select(Address).where(Address.id == address_id))
    if address is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found.",
        )
    if address.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this address.",
        )
    return address


def list_addresses(db: Session, auth_user_id: int) -> list[Address]:
    profile = get_active_profile(db, auth_user_id)
    return list(
        db.scalars(
            select(Address)
            .where(Address.user_id == profile.id)
            .order_by(Address.id)
        )
    )


def get_address(db: Session, auth_user_id: int, address_id: int) -> Address:
    profile = get_active_profile(db, auth_user_id)
    return _owned_address(db, profile.id, address_id)


def _make_default(db: Session, profile_id: int, address_id: int | None = None) -> None:
    statement = update(Address).where(Address.user_id == profile_id)
    if address_id is not None:
        statement = statement.where(Address.id != address_id)
    db.execute(statement.values(is_default=False))


def create_address(db: Session, auth_user_id: int, data: AddressCreate) -> Address:
    profile = _lock_profile(db, auth_user_id)
    values = data.model_dump()
    if values["is_default"]:
        _make_default(db, profile.id)
    address = Address(user_id=profile.id, **values)
    try:
        db.add(address)
        db.commit()
        db.refresh(address)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to save address at this time.",
        ) from exc
    return address


def update_address(
    db: Session, auth_user_id: int, address_id: int, data: AddressUpdate
) -> Address:
    profile = _lock_profile(db, auth_user_id)
    address = _owned_address(db, profile.id, address_id)
    values = data.model_dump()
    if values["is_default"]:
        _make_default(db, profile.id, address.id)
    for field, value in values.items():
        setattr(address, field, value)
    try:
        db.commit()
        db.refresh(address)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to update address at this time.",
        ) from exc
    return address


def delete_address(db: Session, auth_user_id: int, address_id: int) -> None:
    profile = get_active_profile(db, auth_user_id)
    address = _owned_address(db, profile.id, address_id)
    try:
        db.delete(address)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to delete address at this time.",
        ) from exc


def set_default_address(db: Session, auth_user_id: int, address_id: int) -> Address:
    profile = _lock_profile(db, auth_user_id)
    address = _owned_address(db, profile.id, address_id)
    _make_default(db, profile.id, address.id)
    address.is_default = True
    try:
        db.commit()
        db.refresh(address)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to set default address at this time.",
        ) from exc
    return address
