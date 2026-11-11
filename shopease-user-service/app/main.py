"""Application entry point for the ShopEase User Management Service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.security import load_public_key
from app.routers.address_routes import router as address_router
from app.routers.user_routes import router as user_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    load_public_key()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="User profiles and delivery addresses for ShopEase.",
    lifespan=lifespan,
)

app.include_router(user_router, prefix=settings.api_prefix)
app.include_router(address_router, prefix=settings.api_prefix)
