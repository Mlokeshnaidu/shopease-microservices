"""SQLAlchemy model for auditable inventory transactions."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    __table_args__ = (
        CheckConstraint("transaction_type IN ('IN', 'OUT')", name="ck_inventory_transaction_type"),
        CheckConstraint("quantity > 0", name="ck_inventory_quantity_positive"),
        CheckConstraint("previous_stock >= 0", name="ck_inventory_previous_stock_nonnegative"),
        CheckConstraint("updated_stock >= 0", name="ck_inventory_updated_stock_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(3), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="inventory_transactions")
