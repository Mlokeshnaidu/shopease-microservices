import uuid
from datetime import datetime
from typing import Dict, List, Optional
from app.models.product_model import Product
from app.schemas.product_schema import ProductCreate, ProductUpdate


class ProductService:
    """
    Business logic layer for Product operations using in-memory storage.
    Maintains clean separation between HTTP handling and domain operations.
    """

    def __init__(self):
        # In-memory dictionary storing products keyed by product_id
        self._products: Dict[str, Product] = {}

    def _generate_product_id(self) -> str:
        """Generate a clean, collision-free unique Product ID."""
        return f"PROD-{uuid.uuid4().hex[:8].upper()}"

    def create_product(self, product_data: ProductCreate) -> Product:
        """
        Creates and stores a new product in-memory.
        """
        product_id = self._generate_product_id()
        now = datetime.utcnow()

        product = Product(
            product_id=product_id,
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            stock_quantity=product_data.stock_quantity,
            category=product_data.category,
            status=product_data.status.value,
            created_at=now,
            updated_at=None
        )

        self._products[product_id] = product
        return product

    def get_all_products(
        self,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Product]:
        """
        Retrieves products with optional category filtering and pagination.
        """
        products = list(self._products.values())

        # Category filter (case-insensitive)
        if category:
            search_cat = category.strip().lower()
            products = [p for p in products if p.category.strip().lower() == search_cat]

        # Pagination: skip and limit
        return products[skip : skip + limit]

    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """
        Retrieves a single product by its unique ID.
        """
        return self._products.get(product_id)

    def update_product(self, product_id: str, update_data: ProductUpdate) -> Optional[Product]:
        """
        Updates an existing product with new details.
        """
        existing_product = self._products.get(product_id)
        if not existing_product:
            return None

        # Update fields
        existing_product.name = update_data.name
        existing_product.description = update_data.description
        existing_product.price = update_data.price
        existing_product.stock_quantity = update_data.stock_quantity
        existing_product.category = update_data.category
        existing_product.status = update_data.status.value
        existing_product.updated_at = datetime.utcnow()

        return existing_product

    def delete_product(self, product_id: str) -> bool:
        """
        Deletes a product by ID. Returns True if deleted, False if not found.
        """
        if product_id in self._products:
            del self._products[product_id]
            return True
        return False


# Singleton instance of ProductService
product_service = ProductService()

