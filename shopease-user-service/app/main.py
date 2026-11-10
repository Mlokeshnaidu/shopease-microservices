"""Application entry point for the ShopEase User Management Service."""

from fastapi import FastAPI

from app.core.config import settings
from app.routers.address_routes import router as address_router
from app.routers.user_routes import router as user_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="User profiles and delivery addresses for ShopEase.",
)

app.include_router(user_router, prefix=settings.api_prefix)
app.include_router(address_router, prefix=settings.api_prefix)
