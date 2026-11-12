"""Product catalog endpoints, search, filters, and pagination."""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import AdminClaims, CurrentClaims
from app.database.connection import get_db
from app.schemas.product_schema import ProductCreate, ProductDetailResponse, ProductResponse, ProductUpdate
from app.services.product_service import product_service

router = APIRouter(prefix="/products", tags=["Products"])
Database = Annotated[Session, Depends(get_db)]


def _is_admin(claims: dict) -> bool:
    return claims["role"].strip().lower() in {"admin", "administrator"}


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, _claims: AdminClaims, db: Database):
    try:
        return product_service.create(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this SKU already exists.") from None


@router.get("/")
def list_products(
    claims: CurrentClaims,
    db: Database,
    search: str | None = Query(default=None, max_length=150),
    category_id: int | None = Query(default=None, gt=0),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    available: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: Literal["name", "price", "created_at"] = "name",
    sort_order: Literal["asc", "desc"] = "asc",
    include_inactive: bool = False,
):
    admin = _is_admin(claims)
    if include_inactive and not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required.")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="min_price cannot exceed max_price.")
    products, total = product_service.list(
        db,
        search=search,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        available=available,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        include_inactive=include_inactive and admin,
    )
    return {
        "items": products,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product(product_id: int, claims: CurrentClaims, db: Database):
    product = product_service.get(db, product_id)
    if product is None or (
        not _is_admin(claims) and (not product.is_active or not product.category.is_active)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def replace_product(product_id: int, data: ProductCreate, _claims: AdminClaims, db: Database):
    return _update_product(product_id, data, db)


@router.patch("/{product_id}", response_model=ProductResponse)
def patch_product(product_id: int, data: ProductUpdate, _claims: AdminClaims, db: Database):
    return _update_product(product_id, data, db)


def _update_product(product_id: int, data: ProductCreate | ProductUpdate, db: Session):
    product = product_service.get(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    try:
        return product_service.update(db, product, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this SKU already exists.") from None


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_product(product_id: int, _claims: AdminClaims, db: Database):
    product = product_service.get(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    product_service.deactivate(db, product)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
