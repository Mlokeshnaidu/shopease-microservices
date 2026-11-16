"""Customer order endpoints."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_authenticated_claims,
    get_auth_token,
    get_current_user_id,
    require_admin,
)
from app.database.connection import get_db
from app.schemas.order_schema import OrderCreate, OrderListRead, OrderRead, OrderStatusUpdate
from app.services.order_service import (
    cancel_order,
    create_order,
    get_order,
    get_order_by_number,
    list_orders,
    update_order_status,
)

router = APIRouter(prefix="/orders", tags=["orders"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUserId = Annotated[int, Depends(get_current_user_id)]
CurrentClaims = Annotated[dict, Depends(get_authenticated_claims)]
AuthToken = Annotated[str, Depends(get_auth_token)]
AdminClaims = Annotated[dict, Depends(require_admin)]


@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_new_order(
    data: OrderCreate,
    user_id: CurrentUserId,
    token: AuthToken,
    db: DbSession,
):
    order = await create_order(db, user_id, data, token)
    return order


@router.get("/", response_model=OrderListRead)
def read_orders(
    user_id: CurrentUserId,
    claims: CurrentClaims,
    db: DbSession,
    order_status: Literal[
        "PENDING",
        "CONFIRMED",
        "PROCESSING",
        "SHIPPED",
        "DELIVERED",
        "CANCELLED",
    ]
    | None = Query(default=None, alias="status"),
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if created_after is not None and created_before is not None and created_after > created_before:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="created_after must not be later than created_before.",
        )
    is_admin = str(claims.get("role", "")).strip().lower() in {"admin", "administrator"}
    orders, total = list_orders(
        db,
        user_id,
        is_admin=is_admin,
        order_status=order_status,
        created_after=created_after,
        created_before=created_before,
        page=page,
        page_size=page_size,
    )
    return OrderListRead(items=orders, total=total, page=page, page_size=page_size)


@router.get("/number/{order_number}", response_model=OrderRead)
def read_order_by_number(
    order_number: str,
    user_id: CurrentUserId,
    claims: CurrentClaims,
    db: DbSession,
):
    is_admin = str(claims.get("role", "")).strip().lower() in {"admin", "administrator"}
    return get_order_by_number(db, order_number, user_id, is_admin=is_admin)


@router.get("/{order_id}", response_model=OrderRead)
def read_order(order_id: int, user_id: CurrentUserId, claims: CurrentClaims, db: DbSession):
    is_admin = str(claims.get("role", "")).strip().lower() in {"admin", "administrator"}
    return get_order(db, order_id, user_id, is_admin=is_admin)


@router.post("/{order_id}/cancel", response_model=OrderRead)
@router.patch("/{order_id}/cancel", response_model=OrderRead, include_in_schema=False)
async def cancel_existing_order(order_id: int, user_id: CurrentUserId, claims: CurrentClaims, db: DbSession):
    is_admin = str(claims.get("role", "")).strip().lower() in {"admin", "administrator"}
    return await cancel_order(db, order_id, user_id, is_admin=is_admin)


@router.patch("/{order_id}/status", response_model=OrderRead)
async def change_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    _admin: AdminClaims,
    db: DbSession,
):
    if data.order_status == "CANCELLED":
        if data.payment_status == "PAID":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cancelled orders cannot be marked as paid.",
            )
        current_order = get_order(db, order_id, user_id=0, is_admin=True)
        if (
            current_order.order_status == "CANCELLED"
            and current_order.inventory_status == "RELEASED"
        ):
            if data.payment_status in {None, current_order.payment_status}:
                return current_order
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A completed cancellation cannot change payment status.",
            )
        if current_order.payment_status == "PAID":
            if data.payment_status != "REFUNDED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Paid orders must be cancelled and refunded together.",
                )
        elif data.payment_status is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Unpaid cancellations cannot change payment status.",
            )
        order = await cancel_order(
            db,
            order_id,
            user_id=0,
            is_admin=True,
            allow_paid=data.payment_status == "REFUNDED",
        )
        if data.payment_status is None:
            return order
        return update_order_status(
            db,
            order_id,
            OrderStatusUpdate(payment_status=data.payment_status),
        )
    return update_order_status(db, order_id, data)
