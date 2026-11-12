"""SQLAlchemy model for product categories."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="ck_categories_name_not_blank"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    products: Mapped[list["Product"]] = relationship(back_populates="category")
