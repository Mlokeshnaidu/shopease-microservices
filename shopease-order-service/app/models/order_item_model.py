"""Order item persistence model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))
    total_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    order: Mapped["Order"] = relationship(back_populates="items")
