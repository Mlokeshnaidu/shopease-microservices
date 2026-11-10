"""Profile and account endpoints for the authenticated customer."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_user_id
from app.database.connection import get_db
from app.schemas.user_schema import ProfileCreate, ProfileRead, ProfileUpdate
from app.services.user_service import (
    create_profile,
    deactivate_profile,
    delete_profile,
    get_active_profile,
    update_profile,
)

router = APIRouter(prefix="/users", tags=["users"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUserId = Annotated[int, Depends(get_authenticated_user_id)]


@router.post("/profile", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_current_profile(data: ProfileCreate, user_id: CurrentUserId, db: DbSession):
    return create_profile(db, user_id, data)


@router.get("/profile", response_model=ProfileRead)
def read_current_profile(user_id: CurrentUserId, db: DbSession):
    return get_active_profile(db, user_id)


@router.put("/profile", response_model=ProfileRead)
def replace_current_profile(data: ProfileCreate, user_id: CurrentUserId, db: DbSession):
    return update_profile(
        db,
        user_id,
        ProfileUpdate(**data.model_dump()),
    )


@router.patch("/profile", response_model=ProfileRead)
def patch_current_profile(data: ProfileUpdate, user_id: CurrentUserId, db: DbSession):
    return update_profile(db, user_id, data)


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
def remove_current_profile(user_id: CurrentUserId, db: DbSession):
    delete_profile(db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/account/deactivate", response_model=ProfileRead)
def deactivate_current_account(user_id: CurrentUserId, db: DbSession):
    return deactivate_profile(db, user_id)
