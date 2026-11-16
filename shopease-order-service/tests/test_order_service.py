import asyncio
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.connection import Base
from app.models.order_item_model import OrderItem
from app.models.order_model import Order
from app.schemas.order_item_schema import OrderItemCreate
from app.schemas.order_schema import OrderCreate, OrderStatusUpdate
from app.services import order_service
from app.services.order_service import (
    calculate_totals,
    cancel_order,
    create_order,
    get_order,
    update_order_status,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def test_calculate_totals_uses_decimal_discount_before_tax():
    subtotal, discount, shipping, tax, total = calculate_totals(
        Decimal("199.99"),
        discount_amount=Decimal("10.00"),
        shipping_charge=Decimal("10.00"),
        tax_rate=Decimal("0.10"),
    )

    assert subtotal == Decimal("199.99")
    assert discount == Decimal("10.00")
    assert shipping == Decimal("10.00")
    assert tax == Decimal("19.00")
    assert total == Decimal("218.99")


def test_create_order_uses_verified_profile_address_and_discounted_catalog_price(db, monkeypatch):
    async def profile(_token):
        return {"id": 40, "auth_user_id": 7, "is_active": True}

    async def address(_address_id, _token):
        return {
            "id": 8,
            "user_id": 40,
            "address_line_1": "42 Example Street",
            "city": "Example City",
            "country": "Example Country",
        }

    async def product(product_id, _token):
        assert product_id == 12
        return {
            "id": 12,
            "name": "Widget",
            "sku": "WIDGET-12",
            "price": "100.00",
            "discount_price": "80.00",
            "stock_quantity": 4,
            "is_active": True,
        }

    async def reserve(_order_ref, _items):
        return {"status": "RESERVED"}

    monkeypatch.setattr(order_service, "fetch_profile", profile)
    monkeypatch.setattr(order_service, "fetch_address", address)
    monkeypatch.setattr(order_service, "fetch_product", product)
    monkeypatch.setattr(order_service, "reserve_inventory", reserve)

    payload = OrderCreate(
        shipping_address_id=8,
        items=[
            OrderItemCreate(product_id=12, quantity=1),
            OrderItemCreate(product_id=12, quantity=2),
        ],
    )
    order = asyncio.run(create_order(db, user_id=7, payload=payload, token="verified-token"))

    assert order.user_id == 7
    assert order.shipping_address["address_line_1"] == "42 Example Street"
    assert order.subtotal == Decimal("300.00")
    assert order.discount_amount == Decimal("60.00")
    assert order.tax_amount == Decimal("24.00")
    assert order.total_amount == Decimal("274.00")
    assert order.order_status == "PENDING"
    assert order.payment_status == "PENDING"
    assert order.inventory_status == "RESERVED"
    assert len(order.items) == 1
    assert order.items[0].quantity == 3
    assert order.items[0].unit_price == Decimal("100.00")
    assert order.items[0].discount_amount == Decimal("60.00")
    assert order.items[0].total_price == Decimal("240.00")


def test_create_order_rejects_an_address_owned_by_another_profile(db, monkeypatch):
    async def profile(_token):
        return {"id": 40, "auth_user_id": 7, "is_active": True}

    async def address(_address_id, _token):
        return {"id": 8, "user_id": 99}

    monkeypatch.setattr(order_service, "fetch_profile", profile)
    monkeypatch.setattr(order_service, "fetch_address", address)

    payload = OrderCreate(
        shipping_address_id=8,
        items=[OrderItemCreate(product_id=12, quantity=1)],
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(create_order(db, user_id=7, payload=payload, token="verified-token"))

    assert raised.value.status_code == 403
    assert list(db.scalars(select(Order))) == []


def test_create_order_checks_aggregated_quantity_against_stock(db, monkeypatch):
    async def profile(_token):
        return {"id": 40, "auth_user_id": 7, "is_active": True}

    async def address(_address_id, _token):
        return {"id": 8, "user_id": 40}

    async def product(_product_id, _token):
        return {
            "id": 12,
            "name": "Widget",
            "sku": "WIDGET-12",
            "price": "100.00",
            "discount_price": None,
            "stock_quantity": 2,
            "is_active": True,
        }

    async def reserve(_order_ref, _items):
        return {"status": "RESERVED"}

    monkeypatch.setattr(order_service, "fetch_profile", profile)
    monkeypatch.setattr(order_service, "fetch_address", address)
    monkeypatch.setattr(order_service, "fetch_product", product)
    monkeypatch.setattr(order_service, "reserve_inventory", reserve)

    payload = OrderCreate(
        shipping_address_id=8,
        items=[
            OrderItemCreate(product_id=12, quantity=2),
            OrderItemCreate(product_id=12, quantity=1),
        ],
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(create_order(db, user_id=7, payload=payload, token="verified-token"))

    assert raised.value.status_code == 409
    assert list(db.scalars(select(Order))) == []


def test_failed_inventory_reservation_compensates_and_removes_local_order(db, monkeypatch):
    async def profile(_token):
        return {"id": 40, "auth_user_id": 7, "is_active": True}

    async def address(_address_id, _token):
        return {"id": 8, "user_id": 40}

    async def product(_product_id, _token):
        return {
            "id": 12,
            "name": "Widget",
            "sku": "WIDGET-12",
            "price": "100.00",
            "discount_price": None,
            "stock_quantity": 5,
            "is_active": True,
        }

    async def reserve(_order_ref, _items):
        raise HTTPException(status_code=409, detail="Insufficient stock.")

    released = []

    async def release(order_ref, *, allow_missing=False):
        released.append((order_ref, allow_missing))
        return None

    monkeypatch.setattr(order_service, "fetch_profile", profile)
    monkeypatch.setattr(order_service, "fetch_address", address)
    monkeypatch.setattr(order_service, "fetch_product", product)
    monkeypatch.setattr(order_service, "reserve_inventory", reserve)
    monkeypatch.setattr(order_service, "release_inventory", release)

    payload = OrderCreate(
        shipping_address_id=8,
        items=[OrderItemCreate(product_id=12, quantity=1)],
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(create_order(db, user_id=7, payload=payload, token="verified-token"))

    assert raised.value.status_code == 409
    assert len(released) == 1
    assert released[0][1] is True
    assert list(db.scalars(select(Order))) == []
    assert list(db.scalars(select(OrderItem))) == []


def test_failed_reservation_compensation_is_saved_for_retry(db, monkeypatch):
    async def profile(_token):
        return {"id": 40, "auth_user_id": 7, "is_active": True}

    async def address(_address_id, _token):
        return {"id": 8, "user_id": 40}

    async def product(_product_id, _token):
        return {
            "id": 12,
            "name": "Widget",
            "sku": "WIDGET-12",
            "price": "100.00",
            "discount_price": None,
            "stock_quantity": 5,
            "is_active": True,
        }

    async def reserve(_order_ref, _items):
        raise HTTPException(status_code=503, detail="Catalog unavailable.")

    async def failed_release(_order_ref, *, allow_missing=False):
        raise HTTPException(status_code=503, detail="Catalog unavailable.")

    monkeypatch.setattr(order_service, "fetch_profile", profile)
    monkeypatch.setattr(order_service, "fetch_address", address)
    monkeypatch.setattr(order_service, "fetch_product", product)
    monkeypatch.setattr(order_service, "reserve_inventory", reserve)
    monkeypatch.setattr(order_service, "release_inventory", failed_release)

    payload = OrderCreate(
        shipping_address_id=8,
        items=[OrderItemCreate(product_id=12, quantity=1)],
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(create_order(db, user_id=7, payload=payload, token="verified-token"))

    assert raised.value.status_code == 503
    order = db.scalar(select(Order))
    assert order is not None
    assert order.order_status == "CANCELLED"
    assert order.inventory_status == "RELEASE_PENDING"

    async def successful_release(_order_ref, *, allow_missing=False):
        return {"status": "RELEASED"}

    monkeypatch.setattr(order_service, "release_inventory", successful_release)
    cancelled = asyncio.run(cancel_order(db, order.id, user_id=7))
    assert cancelled.order_status == "CANCELLED"
    assert cancelled.inventory_status == "RELEASED"


def test_order_access_and_status_transitions_are_enforced(db, monkeypatch):
    order = Order(
        order_number="ORD-TEST-1",
        user_id=7,
        shipping_address={"city": "Example City"},
        subtotal=Decimal("10.00"),
        discount_amount=Decimal("0.00"),
        shipping_charge=Decimal("10.00"),
        tax_amount=Decimal("1.00"),
        total_amount=Decimal("21.00"),
        order_status="PENDING",
        payment_status="PENDING",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    with pytest.raises(HTTPException) as denied:
        get_order(db, order.id, user_id=8)
    assert denied.value.status_code == 403

    release_calls = []

    async def release(order_ref, *, allow_missing=False):
        release_calls.append((order_ref, allow_missing))
        return {"status": "RELEASED"}

    monkeypatch.setattr(order_service, "release_inventory", release)
    cancelled = asyncio.run(cancel_order(db, order.id, user_id=7))
    assert cancelled.order_status == "CANCELLED"
    assert cancelled.inventory_status == "RELEASED"
    assert cancelled.payment_status == "PENDING"
    assert len(release_calls) == 1

    with pytest.raises(HTTPException) as invalid_transition:
        update_order_status(
            db,
            order.id,
            OrderStatusUpdate(order_status="CONFIRMED"),
        )
    assert invalid_transition.value.status_code == 409


def test_order_status_update_can_advance_pending_order(db):
    order = Order(
        order_number="ORD-TEST-2",
        user_id=7,
        shipping_address={"city": "Example City"},
        subtotal=Decimal("10.00"),
        discount_amount=Decimal("0.00"),
        shipping_charge=Decimal("10.00"),
        tax_amount=Decimal("1.00"),
        total_amount=Decimal("21.00"),
        order_status="PENDING",
        payment_status="PENDING",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    updated = update_order_status(
        db,
        order.id,
        OrderStatusUpdate(order_status="CONFIRMED", payment_status="PAID"),
    )

    assert updated.order_status == "CONFIRMED"
    assert updated.payment_status == "PAID"
    assert len(updated.items) == 0


def test_admin_can_cancel_paid_order_and_record_refund_together(db, monkeypatch):
    order = Order(
        order_number="ORD-TEST-3",
        user_id=7,
        shipping_address={"city": "Example City"},
        subtotal=Decimal("10.00"),
        discount_amount=Decimal("0.00"),
        shipping_charge=Decimal("10.00"),
        tax_amount=Decimal("1.00"),
        total_amount=Decimal("21.00"),
        order_status="PROCESSING",
        payment_status="PAID",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    async def release(_order_ref, *, allow_missing=False):
        return {"status": "RELEASED"}

    monkeypatch.setattr(order_service, "release_inventory", release)
    cancelled = asyncio.run(
        cancel_order(
            db,
            order.id,
            user_id=0,
            is_admin=True,
            allow_paid=True,
        )
    )
    assert cancelled.order_status == "CANCELLED"
    assert cancelled.inventory_status == "RELEASED"

    updated = update_order_status(
        db,
        order.id,
        OrderStatusUpdate(payment_status="REFUNDED"),
    )

    assert updated.order_status == "CANCELLED"
    assert updated.payment_status == "REFUNDED"
