"""Business logic for creating, retrieving, and updating orders."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.order_item_model import OrderItem
from app.models.order_model import Order
from app.schemas.order_schema import OrderCreate, OrderStatusUpdate
from app.services.product_client import (
    fetch_product,
    product_prices,
    release_inventory,
    reserve_inventory,
)
from app.services.user_client import fetch_address, fetch_profile

logger = logging.getLogger(__name__)
CENT = Decimal("0.01")
MAX_ORDER_AMOUNT = Decimal("9999999999.99")
ORDER_TRANSITIONS = {
    "PENDING": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"SHIPPED", "CANCELLED"},
    "SHIPPED": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}
PAYMENT_TRANSITIONS = {
    "PENDING": {"PAID", "FAILED"},
    "PAID": {"REFUNDED"},
    "FAILED": set(),
    "REFUNDED": set(),
}


def round_money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_totals(
    subtotal: Decimal,
    discount_amount: Decimal = Decimal("0.00"),
    shipping_charge: Decimal | None = None,
    tax_rate: Decimal | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    subtotal = round_money(subtotal)
    discount_amount = round_money(discount_amount)
    shipping_cost = round_money(
        settings.default_shipping_charge
        if shipping_charge is None
        else shipping_charge
    )
    effective_tax_rate = settings.tax_rate if tax_rate is None else tax_rate
    if not effective_tax_rate.is_finite() or effective_tax_rate < 0:
        raise ValueError("Tax rate must be a finite non-negative decimal.")
    taxable_amount = subtotal - discount_amount
    if (
        subtotal < 0
        or discount_amount < 0
        or discount_amount > subtotal
        or shipping_cost < 0
        or subtotal > MAX_ORDER_AMOUNT
        or discount_amount > MAX_ORDER_AMOUNT
        or shipping_cost > MAX_ORDER_AMOUNT
    ):
        raise ValueError("Order amounts must be non-negative and discounts cannot exceed subtotal.")
    tax_amount = round_money(taxable_amount * effective_tax_rate)
    total = round_money(taxable_amount + shipping_cost + tax_amount)
    if tax_amount > MAX_ORDER_AMOUNT or total > MAX_ORDER_AMOUNT:
        raise ValueError("Calculated order amount exceeds the supported monetary range.")
    return subtotal, discount_amount, shipping_cost, tax_amount, total


async def create_order(db: Session, user_id: int, payload: OrderCreate, token: str) -> Order:
    profile = await fetch_profile(token)
    try:
        profile_id = int(profile["id"])
        auth_user_id = int(profile["auth_user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="User Management Service returned an invalid profile.",
        ) from exc
    if profile.get("is_active") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The customer profile is inactive.")
    if auth_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Profile does not match the authenticated user.",
        )

    shipping_address = await fetch_address(payload.shipping_address_id, token)
    try:
        address_profile_id = int(shipping_address["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="User Management Service returned an invalid address.",
        ) from exc
    if address_profile_id != profile_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shipping address does not belong to the authenticated user.",
        )

    requested_quantities: dict[int, int] = {}
    for item in payload.items:
        requested_quantities[item.product_id] = (
            requested_quantities.get(item.product_id, 0) + item.quantity
        )
    if any(quantity > 10000 for quantity in requested_quantities.values()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Combined quantity per product cannot exceed 10000.",
        )

    lines: list[dict[str, object]] = []
    subtotal = Decimal("0.00")
    total_discount = Decimal("0.00")
    for product_id, quantity in requested_quantities.items():
        product = await fetch_product(product_id, token)
        try:
            response_product_id = int(product["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Product Catalog Service returned invalid product data.",
            ) from exc
        if response_product_id != product_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Product Catalog Service returned a mismatched product.",
            )

        unit_price, unit_discount = product_prices(product, quantity)
        line_subtotal = round_money(unit_price * quantity)
        line_discount = round_money(unit_discount * quantity)
        line_total = round_money(line_subtotal - line_discount)
        if (
            line_subtotal > MAX_ORDER_AMOUNT
            or line_discount > MAX_ORDER_AMOUNT
            or line_total > MAX_ORDER_AMOUNT
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Calculated item amount exceeds the supported monetary range.",
            )
        subtotal = round_money(subtotal + line_subtotal)
        total_discount = round_money(total_discount + line_discount)
        lines.append(
            {
                "product_id": product_id,
                "product_name": product["name"].strip(),
                "sku": product["sku"].strip(),
                "unit_price": unit_price,
                "quantity": quantity,
                "discount_amount": line_discount,
                "total_price": line_total,
            }
        )

    try:
        subtotal_value, discount_value, shipping_cost, tax_value, total_value = calculate_totals(
            subtotal,
            discount_amount=total_discount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    order = Order(
        order_number=f"ORD-{uuid4().hex.upper()}",
        user_id=user_id,
        shipping_address=shipping_address,
        subtotal=subtotal_value,
        discount_amount=discount_value,
        shipping_charge=shipping_cost,
        tax_amount=tax_value,
        total_amount=total_value,
        order_status="PENDING",
        payment_status="PENDING",
        inventory_status="RESERVING",
        notes=payload.notes,
    )
    try:
        db.add(order)
        db.flush()
        db.add_all(
            [
                OrderItem(order_id=order.id, **line)
                for line in lines
            ]
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.exception("Order creation violated a database constraint.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The order conflicts with an existing record.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Unable to persist the order.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order storage is temporarily unavailable.",
        ) from exc

    order_id = order.id
    try:
        await reserve_inventory(
            order.order_number,
            [
                {"product_id": int(line["product_id"]), "quantity": int(line["quantity"])}
                for line in lines
            ],
        )
    except HTTPException as reservation_error:
        try:
            await release_inventory(order.order_number, allow_missing=True)
        except HTTPException as compensation_error:
            try:
                pending_order = db.get(Order, order_id)
                if pending_order is not None:
                    pending_order.order_status = "CANCELLED"
                    pending_order.inventory_status = "RELEASE_PENDING"
                    db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception("Could not persist pending inventory compensation for %s.", order.order_number)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inventory reservation failed and compensation is pending.",
            ) from compensation_error
        try:
            persisted_order = db.get(Order, order_id)
            if persisted_order is not None:
                db.delete(persisted_order)
                db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Could not remove order after inventory reservation failure.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inventory was released, but failed order cleanup requires reconciliation.",
            ) from exc
        raise reservation_error

    try:
        persisted_order = db.get(Order, order_id)
        if persisted_order is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Order disappeared while inventory was being reserved.",
            )
        persisted_order.inventory_status = "RESERVED"
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not confirm inventory reservation for order %s.", order.order_number)
        try:
            await release_inventory(order.order_number, allow_missing=True)
        except HTTPException:
            logger.exception("Inventory compensation is pending for order %s.", order.order_number)
            try:
                pending_order = db.get(Order, order_id)
                if pending_order is not None:
                    pending_order.order_status = "CANCELLED"
                    pending_order.inventory_status = "RELEASE_PENDING"
                    db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception("Could not persist pending inventory compensation for %s.", order.order_number)
        else:
            try:
                persisted_order = db.get(Order, order_id)
                if persisted_order is not None:
                    db.delete(persisted_order)
                    db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.exception("Could not remove compensated order %s.", order.order_number)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order storage failed after inventory reservation; compensation was attempted.",
        ) from exc

    return get_order(db, order_id, user_id, is_admin=True)


def list_orders(
    db: Session,
    user_id: int,
    is_admin: bool = False,
    *,
    order_status: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Order], int]:
    filters = []
    if not is_admin:
        filters.append(Order.user_id == user_id)
    if order_status is not None:
        filters.append(Order.order_status == order_status)
    if created_after is not None:
        filters.append(Order.created_at >= created_after)
    if created_before is not None:
        filters.append(Order.created_at <= created_before)

    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    statement = (
        select(Order)
        .options(selectinload(Order.items))
        .where(*filters)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(db.scalars(statement)), total


def get_order(db: Session, order_id: int, user_id: int, is_admin: bool = False) -> Order:
    statement = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = db.scalar(statement)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if not is_admin and order.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to access this order.",
        )
    return order


def get_order_by_number(
    db: Session,
    order_number: str,
    user_id: int,
    is_admin: bool = False,
) -> Order:
    order_id = db.scalar(select(Order.id).where(Order.order_number == order_number))
    if order_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return get_order(db, order_id, user_id, is_admin=is_admin)


async def cancel_order(
    db: Session,
    order_id: int,
    user_id: int,
    is_admin: bool = False,
    *,
    allow_paid: bool = False,
) -> Order:
    order = get_order(db, order_id, user_id, is_admin=is_admin)
    if order.order_status == "CANCELLED" and order.inventory_status == "RELEASED":
        return order
    if order.order_status not in {"PENDING", "CONFIRMED", "PROCESSING", "CANCELLED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shipped or delivered orders cannot be cancelled.",
        )
    if order.payment_status == "PAID" and not allow_paid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Paid orders must be cancelled and refunded by an administrator.",
        )

    if order.inventory_status != "RELEASE_PENDING":
        order.inventory_status = "RELEASE_PENDING"
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Unable to record cancellation request for %s.", order.order_number)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to record the inventory release request.",
            ) from exc

    await release_inventory(order.order_number, allow_missing=True)
    order = get_order(db, order_id, user_id, is_admin=is_admin)
    order.order_status = "CANCELLED"
    order.inventory_status = "RELEASED"
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Unable to cancel order %s.", order.order_number)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order storage is temporarily unavailable.",
        ) from exc
    return get_order(db, order_id, user_id, is_admin=is_admin)


def update_order_status(
    db: Session,
    order_id: int,
    update: OrderStatusUpdate,
) -> Order:
    order = get_order(db, order_id, user_id=0, is_admin=True)
    if update.order_status is not None:
        if update.order_status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Use the cancellation workflow to release reserved inventory.",
            )
        if order.inventory_status != "RESERVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order status cannot advance until inventory is reserved.",
            )
        if update.order_status not in ORDER_TRANSITIONS[order.order_status]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Order cannot transition from {order.order_status} to {update.order_status}.",
            )
    if update.payment_status is not None:
        if (
            update.payment_status in {"PAID", "FAILED"}
            and order.inventory_status != "RESERVED"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment cannot be finalized until inventory is reserved.",
            )
        if update.payment_status == "REFUNDED" and order.inventory_status != "RELEASED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inventory must be released before a refund is recorded.",
            )
        if update.payment_status not in PAYMENT_TRANSITIONS[order.payment_status]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Payment cannot transition from {order.payment_status} to {update.payment_status}.",
            )
        if update.payment_status == "PAID" and order.order_status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cancelled orders cannot be marked as paid.",
            )
        if update.payment_status == "REFUNDED" and order.order_status != "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only cancelled orders can be refunded.",
            )

    if update.order_status is not None:
        order.order_status = update.order_status
    if update.payment_status is not None:
        order.payment_status = update.payment_status

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Unable to update order status for %s.", order.order_number)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Order storage is temporarily unavailable.",
        ) from exc
    return get_order(db, order_id, user_id=0, is_admin=True)
