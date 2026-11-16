from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.database.connection import Base, get_db
from app.main import app
from app.models.order_model import Order
from app.services import order_service


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    key_path = tmp_path / "jwt_public.pem"
    key_path.write_text(public_key, encoding="ascii")
    monkeypatch.setattr(settings, "jwt_public_key_file", key_path)
    monkeypatch.setattr(security, "_read_public_key", lambda _path: public_key)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

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
        return {
            "id": product_id,
            "name": "Widget",
            "sku": "WIDGET-12",
            "price": "100.00",
            "discount_price": "80.00",
            "stock_quantity": 5,
            "is_active": True,
        }

    reservation_calls = []
    release_calls = []

    async def reserve(order_ref, items):
        reservation_calls.append((order_ref, items))
        return {
            "order_ref": order_ref,
            "status": "RESERVED",
            "items": sorted(items, key=lambda item: item["product_id"]),
        }

    async def release(order_ref, *, allow_missing=False):
        release_calls.append((order_ref, allow_missing))
        return {"order_ref": order_ref, "status": "RELEASED"}

    monkeypatch.setattr(order_service, "fetch_profile", profile)
    monkeypatch.setattr(order_service, "fetch_address", address)
    monkeypatch.setattr(order_service, "fetch_product", product)
    monkeypatch.setattr(order_service, "reserve_inventory", reserve)
    monkeypatch.setattr(order_service, "release_inventory", release)

    def token(user_id=7, role="user"):
        issued_at = datetime.now(timezone.utc)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "iat": issued_at,
                "exp": issued_at + timedelta(minutes=5),
                "iss": "shopease-auth-service",
                "aud": "shopease-services",
            },
            private_pem,
            algorithm="RS256",
        )

    try:
        with TestClient(app) as client:
            yield client, session, token, reservation_calls, release_calls
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_order_api_auth_creation_history_ownership_and_admin_status(api_client):
    client, db, token, reservation_calls, release_calls = api_client

    assert client.get("/api/orders/").status_code == 401
    assert client.get("/api/orders/", headers={"Authorization": "Bearer invalid"}).status_code == 401

    user_headers = {"Authorization": f"Bearer {token()}"}
    response = client.post(
        "/api/orders/",
        headers=user_headers,
        json={
            "shipping_address_id": 8,
            "notes": "  Leave at the door  ",
            "items": [
                {"product_id": 12, "quantity": 1},
                {"product_id": 12, "quantity": 2},
            ],
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["user_id"] == 7
    assert created["notes"] == "Leave at the door"
    assert created["order_status"] == "PENDING"
    assert created["payment_status"] == "PENDING"
    assert created["inventory_status"] == "RESERVED"
    assert Decimal(str(created["total_amount"])) == Decimal("274.00")
    assert len(created["items"]) == 1
    assert created["items"][0]["quantity"] == 3
    assert len(reservation_calls) == 1
    assert reservation_calls[0][1] == [{"product_id": 12, "quantity": 3}]

    other_order = Order(
        order_number="ORD-OTHER-USER",
        user_id=8,
        shipping_address={"city": "Other City"},
        subtotal=Decimal("10.00"),
        discount_amount=Decimal("0.00"),
        shipping_charge=Decimal("10.00"),
        tax_amount=Decimal("1.00"),
        total_amount=Decimal("21.00"),
        order_status="PENDING",
        payment_status="PENDING",
    )
    db.add(other_order)
    db.commit()
    db.refresh(other_order)

    user_orders = client.get("/api/orders/", headers=user_headers)
    assert user_orders.status_code == 200
    assert user_orders.json()["total"] == 1
    assert len(user_orders.json()["items"]) == 1
    paged_orders = client.get("/api/orders/?status=PENDING&page=1&page_size=1", headers=user_headers)
    assert paged_orders.status_code == 200
    assert paged_orders.json()["page_size"] == 1
    assert client.get(
        f"/api/orders/number/{created['order_number']}",
        headers=user_headers,
    ).status_code == 200
    assert client.get(
        "/api/orders/?status=DELIVERED",
        headers=user_headers,
    ).json()["total"] == 0
    assert client.get(
        "/api/orders/?created_after=2099-01-01T00:00:00Z",
        headers=user_headers,
    ).json()["total"] == 0
    assert client.get(f"/api/orders/{other_order.id}", headers=user_headers).status_code == 403
    assert client.get(f"/api/orders/{created['id']}/items", headers=user_headers).status_code == 200

    admin_headers = {"Authorization": f"Bearer {token(role='admin')}"}
    admin_orders = client.get("/api/orders/", headers=admin_headers)
    assert admin_orders.status_code == 200
    assert len(admin_orders.json()["items"]) == 2
    admin_page = client.get(
        "/api/orders/?page=1&page_size=1",
        headers=admin_headers,
    )
    assert admin_page.status_code == 200
    assert admin_page.json()["total"] == 2
    assert len(admin_page.json()["items"]) == 1
    status_update = client.patch(
        f"/api/orders/{created['id']}/status",
        headers=admin_headers,
        json={"order_status": "CONFIRMED", "payment_status": "PAID"},
    )
    assert status_update.status_code == 200, status_update.text
    assert status_update.json()["order_status"] == "CONFIRMED"
    assert status_update.json()["payment_status"] == "PAID"

    incomplete_refund = client.patch(
        f"/api/orders/{created['id']}/status",
        headers=admin_headers,
        json={"order_status": "CANCELLED"},
    )
    assert incomplete_refund.status_code == 409
    assert release_calls == []

    refund_update = client.patch(
        f"/api/orders/{created['id']}/status",
        headers=admin_headers,
        json={"order_status": "CANCELLED", "payment_status": "REFUNDED"},
    )
    assert refund_update.status_code == 200, refund_update.text
    assert refund_update.json()["order_status"] == "CANCELLED"
    assert refund_update.json()["payment_status"] == "REFUNDED"
    assert len(release_calls) == 1

    unpaid_order = client.post(
        "/api/orders/",
        headers=user_headers,
        json={
            "shipping_address_id": 8,
            "items": [{"product_id": 12, "quantity": 1}],
        },
    )
    assert unpaid_order.status_code == 201, unpaid_order.text
    invalid_refund = client.patch(
        f"/api/orders/{unpaid_order.json()['id']}/status",
        headers=admin_headers,
        json={"order_status": "CANCELLED", "payment_status": "REFUNDED"},
    )
    assert invalid_refund.status_code == 409
    assert len(release_calls) == 1

    assert client.patch(
        f"/api/orders/{other_order.id}/status",
        headers=user_headers,
        json={"order_status": "CONFIRMED"},
    ).status_code == 403


def test_order_cancellation_is_idempotent(api_client):
    client, _db, token, _reservations, release_calls = api_client
    headers = {"Authorization": f"Bearer {token()}"}
    response = client.post(
        "/api/orders/",
        headers=headers,
        json={
            "shipping_address_id": 8,
            "items": [{"product_id": 12, "quantity": 1}],
        },
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["id"]

    first_cancel = client.post(f"/api/orders/{order_id}/cancel", headers=headers)
    second_cancel = client.post(f"/api/orders/{order_id}/cancel", headers=headers)

    assert first_cancel.status_code == 200, first_cancel.text
    assert second_cancel.status_code == 200, second_cancel.text
    assert first_cancel.json()["order_status"] == "CANCELLED"
    assert first_cancel.json()["inventory_status"] == "RELEASED"
    assert len(release_calls) == 1


def test_shipped_order_cannot_be_cancelled(api_client):
    client, _db, token, _reservations, release_calls = api_client
    user_headers = {"Authorization": f"Bearer {token()}"}
    response = client.post(
        "/api/orders/",
        headers=user_headers,
        json={
            "shipping_address_id": 8,
            "items": [{"product_id": 12, "quantity": 1}],
        },
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["id"]
    admin_headers = {"Authorization": f"Bearer {token(role='admin')}"}

    for next_status in ("CONFIRMED", "PROCESSING", "SHIPPED"):
        update = client.patch(
            f"/api/orders/{order_id}/status",
            headers=admin_headers,
            json={"order_status": next_status},
        )
        assert update.status_code == 200, update.text

    cancelled = client.post(f"/api/orders/{order_id}/cancel", headers=user_headers)
    assert cancelled.status_code == 409
    assert release_calls == []


@pytest.mark.parametrize(
    ("catalog_result", "expected_status"),
    [
        (HTTPException(status_code=404, detail="Product not found."), 404),
        (
            {
                "id": 12,
                "name": "Inactive Widget",
                "sku": "INACTIVE-12",
                "price": "100.00",
                "discount_price": None,
                "stock_quantity": 5,
                "is_active": False,
            },
            400,
        ),
        (
            {
                "id": 12,
                "name": "Widget",
                "sku": "WIDGET-12",
                "price": "100.00",
                "discount_price": None,
                "stock_quantity": 0,
                "is_active": True,
            },
            409,
        ),
    ],
)
def test_order_creation_rejects_invalid_inactive_or_out_of_stock_products(
    api_client,
    monkeypatch,
    catalog_result,
    expected_status,
):
    client, db, token, reservation_calls, _release_calls = api_client

    async def product(_product_id, _token):
        if isinstance(catalog_result, HTTPException):
            raise catalog_result
        return catalog_result

    monkeypatch.setattr(order_service, "fetch_product", product)
    response = client.post(
        "/api/orders/",
        headers={"Authorization": f"Bearer {token()}"},
        json={
            "shipping_address_id": 8,
            "items": [{"product_id": 12, "quantity": 1}],
        },
    )

    assert response.status_code == expected_status
    assert list(db.scalars(select(Order))) == []
    assert reservation_calls == []


def test_order_creation_rejects_unavailable_shipping_address(api_client, monkeypatch):
    client, db, token, reservation_calls, _release_calls = api_client

    async def address(_address_id, _token):
        raise HTTPException(status_code=404, detail="Shipping address not found.")

    monkeypatch.setattr(order_service, "fetch_address", address)
    response = client.post(
        "/api/orders/",
        headers={"Authorization": f"Bearer {token()}"},
        json={
            "shipping_address_id": 999,
            "items": [{"product_id": 12, "quantity": 1}],
        },
    )

    assert response.status_code == 404
    assert list(db.scalars(select(Order))) == []
    assert reservation_calls == []
