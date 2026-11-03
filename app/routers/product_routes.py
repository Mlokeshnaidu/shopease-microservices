from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query

from app.schemas.product_schema import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    MessageResponse,
)
from app.services.product_service import product_service

# ---------------------------------------------------------------------------
# Router Definition
# ---------------------------------------------------------------------------
router = APIRouter(
    prefix="/products",
    tags=["Products"],
    responses={
        404: {"description": "Product Not Found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


# ---------------------------------------------------------------------------
# API 1: Create Product
# POST /api/products/
# ---------------------------------------------------------------------------
@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a New Product",
    description=(
        "Accepts a JSON request body with product details, validates all fields using "
        "Pydantic, generates a unique Product ID, stores the product in memory, and "
        "returns the newly created product with HTTP 201."
    ),
)
def create_product(product_data: ProductCreate):
    """
    Create a new product and persist it in the in-memory store.
    """
    try:
        new_product = product_service.create_product(product_data)
        return new_product.to_dict()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while creating the product: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# API 2: Retrieve All Products
# GET /api/products/
# ---------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve All Products",
    description=(
        "Returns a paginated list of all products stored in memory. Supports optional "
        "filtering by category (case-insensitive), as well as 'skip' and 'limit' query "
        "parameters for pagination. Returns an empty list when no products exist."
    ),
)
def get_all_products(
    category: Optional[str] = Query(
        default=None,
        description="Filter products by category name (case-insensitive).",
        examples=["Electronics"],
    ),
    skip: int = Query(
        default=0,
        ge=0,
        description="Number of products to skip (for pagination). Must be >= 0.",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of products to return. Between 1 and 500.",
    ),
):
    """
    Retrieve all products with optional category filtering and pagination.
    """
    try:
        products = product_service.get_all_products(category=category, skip=skip, limit=limit)
        return [p.to_dict() for p in products]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving products: {str(exc)}",
        )


# ---------------------------------------------------------------------------
# API 3: Retrieve Product by ID
# GET /api/products/{product_id}
# ---------------------------------------------------------------------------
@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a Product by ID",
    description=(
        "Accepts a product ID as a URL path parameter. Returns the matching product "
        "details if found. Returns HTTP 404 if the product does not exist."
    ),
)
def get_product_by_id(product_id: str):
    """
    Retrieve a single product by its unique product_id.
    """
    if not product_id or not product_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product ID must not be empty.",
        )

    product = product_service.get_product_by_id(product_id.strip())
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found.",
        )
    return product.to_dict()


# ---------------------------------------------------------------------------
# API 4: Update Product
# PUT /api/products/{product_id}
# ---------------------------------------------------------------------------
@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an Existing Product",
    description=(
        "Accepts a product ID as a URL path parameter and updated product details in the "
        "request body. Updates the product in memory and returns the updated data. "
        "Returns HTTP 404 if the product does not exist."
    ),
)
def update_product(product_id: str, update_data: ProductUpdate):
    """
    Update a product fully (PUT-style replacement) with the provided data.
    """
    if not product_id or not product_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product ID must not be empty.",
        )

    updated_product = product_service.update_product(product_id.strip(), update_data)
    if not updated_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found. Cannot update.",
        )
    return updated_product.to_dict()


# ---------------------------------------------------------------------------
# API 5: Delete Product
# DELETE /api/products/{product_id}
# ---------------------------------------------------------------------------
@router.delete(
    "/{product_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a Product by ID",
    description=(
        "Accepts a product ID as a URL path parameter. Deletes the matching product from "
        "memory and returns a confirmation message. Returns HTTP 404 if the product does "
        "not exist."
    ),
)
def delete_product(product_id: str):
    """
    Delete a product from the in-memory store by its product_id.
    """
    if not product_id or not product_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product ID must not be empty.",
        )

    deleted = product_service.delete_product(product_id.strip())
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found. Cannot delete.",
        )
    return {"message": f"Product with ID '{product_id}' has been successfully deleted."}

