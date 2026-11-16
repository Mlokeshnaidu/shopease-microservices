"""Order item endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_claims, get_current_user_id
from app.database.connection import get_db
from app.schemas.order_item_schema import OrderItemRead
from app.services.order_service import get_order

router = APIRouter(prefix="/orders", tags=["order-items"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUserId = Annotated[int, Depends(get_current_user_id)]
Claims = Annotated[dict, Depends(get_authenticated_claims)]


@router.get("/{order_id}/items", response_model=list[OrderItemRead], status_code=status.HTTP_200_OK)
def read_order_items(order_id: int, user_id: CurrentUserId, claims: Claims, db: DbSession):
    is_admin = str(claims.get("role", "")).strip().lower() in {"admin", "administrator"}
    order = get_order(db, order_id, user_id, is_admin=is_admin)
    return order.items
