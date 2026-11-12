"""SQLAlchemy model for catalog products."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        CheckConstraint("discount_price IS NULL OR (discount_price > 0 AND discount_price <= price)", name="ck_products_discount_price"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_nonnegative"),
        CheckConstraint("length(trim(name)) > 0", name="ck_products_name_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    image_url: Mapped[str | None] = mapped_column(String(2048))
    brand: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    category: Mapped["Category"] = relationship(back_populates="products")
    inventory_transactions: Mapped[list["InventoryTransaction"]] = relationship(back_populates="product")
