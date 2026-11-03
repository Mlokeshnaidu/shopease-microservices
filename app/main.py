"""
ShopEase Product Service - FastAPI Application Entry Point
Initializes the FastAPI application, registers routers and exception handlers.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config.settings import settings
from app.routers.product_routes import router as product_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shopease.product-service")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Product Management Microservice for ShopEase.",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors (HTTP 422)."""
    errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "field": field_path or "request body",
            "message": error["msg"],
            "invalid_value": error.get("input"),
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Failed",
            "detail": "One or more fields failed validation.",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected server errors (HTTP 500)."""
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please try again later.",
        },
    )


app.include_router(product_router, prefix=settings.API_PREFIX)