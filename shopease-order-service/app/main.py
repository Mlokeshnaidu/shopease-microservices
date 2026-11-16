"""FastAPI application entry point for the ShopEase Order Service."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.routers.order_item_routes import router as order_item_router
from app.routers.order_routes import router as order_router

logger = logging.getLogger("shopease.order")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    pem = Path(settings.jwt_public_key_file).read_text(encoding="ascii")
    key = serialization.load_pem_public_key(pem.encode("ascii"))
    if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
        raise ValueError("JWT public key must be an RSA key of at least 2048 bits.")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Order management microservice for ShopEase.",
    lifespan=lifespan,
)


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database failure on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Order storage is temporarily unavailable."},
    )


app.include_router(order_router, prefix=settings.api_prefix)
app.include_router(order_item_router, prefix=settings.api_prefix)
