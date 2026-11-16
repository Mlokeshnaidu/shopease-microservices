"""Order persistence model."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DECIMAL, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    shipping_address: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))
    discount_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))
    shipping_charge: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))
    tax_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=Decimal("0.00"))
    order_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    inventory_status: Mapped[str] = mapped_column(String(32), nullable=False, default="RESERVED")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
