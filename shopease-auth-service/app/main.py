"""Application entry point for the ShopEase Authentication Service."""

from fastapi import FastAPI

from app.core.config import settings
from app.routers.auth_routes import router as auth_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Authentication microservice for ShopEase.",
)

app.include_router(auth_router, prefix=settings.api_prefix)
