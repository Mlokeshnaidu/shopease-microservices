"""Idempotent order inventory reservations."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        UniqueConstraint("order_ref", "product_id", name="uq_inventory_reservation_order_product"),
        CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity_positive"),
        CheckConstraint("status IN ('RESERVED', 'RELEASED')", name="ck_inventory_reservation_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RESERVED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
