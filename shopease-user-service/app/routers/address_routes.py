"""Address endpoints for the authenticated customer."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_user_id
from app.database.connection import get_db
from app.schemas.address_schema import (
    AddressCreate,
    AddressRead,
    AddressUpdate,
)
from app.services.address_service import (
    create_address,
    delete_address,
    get_address,
    list_addresses,
    set_default_address,
    update_address,
)

router = APIRouter(prefix="/users/addresses", tags=["addresses"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUserId = Annotated[int, Depends(get_authenticated_user_id)]


@router.post("", response_model=AddressRead, status_code=status.HTTP_201_CREATED)
def add_address(data: AddressCreate, user_id: CurrentUserId, db: DbSession):
    return create_address(db, user_id, data)


@router.get("", response_model=list[AddressRead])
def read_addresses(user_id: CurrentUserId, db: DbSession):
    return list_addresses(db, user_id)


@router.get("/{address_id}", response_model=AddressRead)
def read_address(address_id: int, user_id: CurrentUserId, db: DbSession):
    return get_address(db, user_id, address_id)


@router.put("/{address_id}", response_model=AddressRead)
def replace_address(
    address_id: int, data: AddressUpdate, user_id: CurrentUserId, db: DbSession
):
    return update_address(db, user_id, address_id, data)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_address(address_id: int, user_id: CurrentUserId, db: DbSession):
    delete_address(db, user_id, address_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{address_id}/default", response_model=AddressRead)
def make_default_address(
    address_id: int,
    user_id: CurrentUserId,
    db: DbSession,
):
    return set_default_address(db, user_id, address_id)
