"""HTTP client wrappers for the User Management Service."""

from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


async def _get_user_resource(url: str, token: str, resource: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"User Management Service timed out while retrieving {resource}.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User Management Service is unavailable.",
        ) from exc

    if response.status_code in {401, 403, 404}:
        detail = {
            401: "The User Management Service rejected the supplied credentials.",
            403: f"The {resource} is not accessible to the authenticated user.",
            404: f"{resource.capitalize()} not found.",
        }[response.status_code]
        raise HTTPException(status_code=response.status_code, detail=detail)
    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User Management Service is unavailable.",
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="User Management Service rejected the request.",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="User Management Service returned invalid JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="User Management Service returned an invalid response.",
        )
    return payload


async def fetch_profile(token: str) -> dict[str, Any]:
    url = f"{settings.user_service_url.rstrip('/')}/api/users/profile"
    return await _get_user_resource(url, token, "user profile")


async def fetch_address(address_id: int, token: str) -> dict[str, Any]:
    url = (
        f"{settings.user_service_url.rstrip('/')}"
        f"/api/users/addresses/{address_id}"
    )
    return await _get_user_resource(url, token, "shipping address")
