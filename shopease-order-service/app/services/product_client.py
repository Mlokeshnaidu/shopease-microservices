"""HTTP client wrappers for the Product Catalog Service."""

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


async def fetch_product(product_id: int, token: str) -> dict[str, Any]:
    url = f"{settings.product_service_url.rstrip('/')}/api/products/{product_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product Catalog Service timed out.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product Catalog Service is unavailable.",
        ) from exc

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive.")
    if response.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        raise HTTPException(
            status_code=response.status_code,
            detail="Product Catalog Service rejected the supplied credentials.",
        )
    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product Catalog Service is unavailable.",
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service rejected the product request.",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service returned invalid JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid product response.")
    return payload


def product_prices(product: dict[str, Any], quantity: int) -> tuple[Decimal, Decimal]:
    if product.get("is_active") is not True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product is inactive.")

    try:
        stock_quantity = int(product["stock_quantity"])
        list_price = Decimal(str(product["price"]))
        discount_price_raw = product.get("discount_price")
        sale_price = (
            Decimal(str(discount_price_raw))
            if discount_price_raw is not None
            else list_price
        )
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service returned invalid product data.",
        ) from exc

    if (
        stock_quantity < 0
        or not list_price.is_finite()
        or not sale_price.is_finite()
        or list_price <= 0
        or sale_price <= 0
        or sale_price > list_price
        or not isinstance(product.get("name"), str)
        or not product["name"].strip()
        or not isinstance(product.get("sku"), str)
        or not product["sku"].strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service returned invalid product data.",
        )
    if quantity > stock_quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Requested quantity exceeds available stock for product {product.get('id')}.",
        )

    return list_price.quantize(Decimal("0.01")), (list_price - sale_price).quantize(Decimal("0.01"))


async def _reservation_request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    allow_missing: bool = False,
) -> dict[str, Any] | None:
    api_key = settings.catalog_service_api_key.get_secret_value()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product Catalog inventory integration is not configured.",
        )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method,
                url,
                headers={"X-Order-Service-Key": api_key},
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product Catalog Service timed out during inventory processing.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product Catalog Service is unavailable during inventory processing.",
        ) from exc

    if allow_missing and response.status_code == status.HTTP_404_NOT_FOUND:
        return None
    if response.status_code == status.HTTP_409_CONFLICT:
        try:
            detail = response.json().get("detail", "Insufficient inventory.")
        except ValueError:
            detail = "Insufficient inventory."
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Product Catalog Service is unavailable during inventory processing.",
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service rejected the inventory operation.",
        )
    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service returned invalid inventory data.",
        ) from exc
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service returned invalid inventory data.",
        )
    return result


async def reserve_inventory(order_ref: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    result = await _reservation_request(
        "POST",
        f"{settings.product_service_url.rstrip('/')}/api/inventory/reservations",
        payload={"order_ref": order_ref, "items": items},
    )
    expected_items = sorted(items, key=lambda item: item["product_id"])
    if (
        result is None
        or result.get("status") != "RESERVED"
        or result.get("order_ref") != order_ref
        or result.get("items") != expected_items
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service did not confirm the inventory reservation.",
        )
    return result


async def release_inventory(
    order_ref: str,
    *,
    allow_missing: bool = False,
) -> dict[str, Any] | None:
    result = await _reservation_request(
        "POST",
        f"{settings.product_service_url.rstrip('/')}/api/inventory/reservations/{order_ref}/release",
        allow_missing=allow_missing,
    )
    if result is not None and result.get("status") != "RELEASED":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service did not confirm the inventory release.",
        )
    if result is not None and result.get("order_ref") != order_ref:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Product Catalog Service returned a mismatched inventory operation.",
        )
    return result
