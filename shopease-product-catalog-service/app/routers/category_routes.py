"""Category management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import AdminClaims, CurrentClaims
from app.database.connection import get_db
from app.models.category_model import Category
from app.schemas.category_schema import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category_service import category_service

router = APIRouter(prefix="/categories", tags=["Categories"])
Database = Annotated[Session, Depends(get_db)]


def _is_admin(claims: dict) -> bool:
    return claims["role"].strip().lower() in {"admin", "administrator"}


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, _claims: AdminClaims, db: Database):
    try:
        return category_service.create(db, data)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A category with this name already exists.") from None


@router.get("/", response_model=list[CategoryResponse])
def list_categories(
    claims: CurrentClaims,
    db: Database,
    include_inactive: bool = False,
):
    if include_inactive and not _is_admin(claims):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    return category_service.list(db, include_inactive=include_inactive)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, claims: CurrentClaims, db: Database):
    category = category_service.get(db, category_id)
    if category is None or (not _is_admin(claims) and not category.is_active):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return category


@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(category_id: int, data: CategoryUpdate, _claims: AdminClaims, db: Database):
    category = category_service.get(db, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    try:
        return category_service.update(db, category, data)
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A category with this name already exists.") from None


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, _claims: AdminClaims, db: Database):
    category = category_service.get(db, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    try:
        category_service.delete(db, category)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
