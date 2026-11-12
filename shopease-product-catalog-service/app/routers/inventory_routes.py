"""Stock operations and transaction history endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import AdminClaims
from app.database.connection import get_db
from app.models.product_model import Product
from app.schemas.inventory_schema import InventoryResponse, InventoryTransactionResponse, StockAdjustment
from app.schemas.product_schema import ProductResponse
from app.services.inventory_service import inventory_service

router = APIRouter(prefix="/inventory", tags=["Inventory"])
Database = Annotated[Session, Depends(get_db)]


def _stock_response(product: Product) -> dict[str, int | str | bool]:
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "stock_quantity": product.stock_quantity,
        "available": product.is_active and product.stock_quantity > 0,
    }


@router.get("/low-stock", response_model=list[ProductResponse])
def list_low_stock(
    _claims: AdminClaims,
    db: Database,
    threshold: int | None = Query(default=None, ge=0),
):
    return inventory_service.low_stock(db, threshold)


@router.get("/{product_id}", response_model=InventoryResponse)
def get_inventory(product_id: int, _claims: AdminClaims, db: Database):
    product = inventory_service.get_stock(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return _stock_response(product)


@router.post("/{product_id}/stock-in", response_model=InventoryResponse)
def stock_in(product_id: int, data: StockAdjustment, _claims: AdminClaims, db: Database):
    return _adjust(product_id, data, "IN", db)


@router.post("/{product_id}/stock-out", response_model=InventoryResponse)
def stock_out(product_id: int, data: StockAdjustment, _claims: AdminClaims, db: Database):
    return _adjust(product_id, data, "OUT", db)


def _adjust(product_id: int, data: StockAdjustment, transaction_type: Literal["IN", "OUT"], db: Session):
    try:
        product = inventory_service.adjust(db, product_id, data, transaction_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return _stock_response(product)


@router.get("/{product_id}/history", response_model=list[InventoryTransactionResponse])
def get_inventory_history(product_id: int, _claims: AdminClaims, db: Database):
    product = inventory_service.get_stock(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return inventory_service.history(db, product_id)
