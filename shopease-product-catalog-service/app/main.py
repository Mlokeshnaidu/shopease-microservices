"""FastAPI application for the ShopEase Product Catalog Service."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import settings
from app.routers.category_routes import router as category_router
from app.routers.inventory_routes import router as inventory_router
from app.routers.product_routes import router as product_router

logger = logging.getLogger("shopease.product-catalog")

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    logger.info("Constraint violation on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "The request conflicts with an existing catalog record."},
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database failure on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database operation failed."},
    )


app.include_router(product_router, prefix=settings.api_prefix)
app.include_router(category_router, prefix=settings.api_prefix)
app.include_router(inventory_router, prefix=settings.api_prefix)
