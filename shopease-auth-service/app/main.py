"""Application entry point for the ShopEase Authentication Service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.security import validate_signing_key_pair
from app.routers.auth_routes import router as auth_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_signing_key_pair()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Authentication microservice for ShopEase.",
    lifespan=lifespan,
)

app.include_router(auth_router, prefix=settings.api_prefix)
