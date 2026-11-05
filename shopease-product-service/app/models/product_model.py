from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Product:
    """
    In-memory domain model representing a Product entity in ShopEase.
    """
    product_id: str
    name: str
    description: Optional[str]
    price: float
    stock_quantity: int
    category: str
    status: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert product model instance to dictionary."""
        return {
            "product_id": self.product_id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "stock_quantity": self.stock_quantity,
            "category": self.category,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

