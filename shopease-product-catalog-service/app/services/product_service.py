"""Database operations and catalog querying for products."""

from decimal import Decimal
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.category_model import Category
from app.models.inventory_model import InventoryTransaction
from app.models.product_model import Product
from app.schemas.product_schema import ProductCreate, ProductUpdate


class ProductService:
    def create(self, db: Session, data: ProductCreate) -> Product:
        category = db.get(Category, data.category_id)
        if category is None or not category.is_active:
            raise ValueError("Category does not exist or is inactive.")

        payload = data.model_dump()
        payload["image_url"] = str(payload["image_url"]) if payload["image_url"] is not None else None
        product = Product(**payload)
        db.add(product)
        try:
            db.flush()
            if product.stock_quantity:
                db.add(
                    InventoryTransaction(
                        product_id=product.id,
                        transaction_type="IN",
                        quantity=product.stock_quantity,
                        previous_stock=0,
                        updated_stock=product.stock_quantity,
                        remarks="Initial stock at product creation",
                    )
                )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        db.refresh(product)
        return product

    def list(
        self,
        db: Session,
        *,
        search: str | None,
        category_id: int | None,
        min_price: Decimal | None,
        max_price: Decimal | None,
        available: bool | None,
        page: int,
        page_size: int,
        sort_by: Literal["name", "price", "created_at"],
        sort_order: Literal["asc", "desc"],
        include_inactive: bool,
    ) -> tuple[list[Product], int]:
        filters = []
        if not include_inactive:
            filters.extend((Product.is_active.is_(True), Category.is_active.is_(True)))
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
        if category_id is not None:
            filters.append(Product.category_id == category_id)
        if min_price is not None:
            filters.append(Product.price >= min_price)
        if max_price is not None:
            filters.append(Product.price <= max_price)
        if available is True:
            filters.append(Product.stock_quantity > 0)
        elif available is False:
            filters.append(Product.stock_quantity == 0)

        total = (
            db.scalar(
                select(func.count(Product.id))
                .select_from(Product)
                .join(Category, Product.category_id == Category.id)
                .where(*filters)
            )
            or 0
        )
        column = {"name": Product.name, "price": Product.price, "created_at": Product.created_at}[sort_by]
        column = column.asc() if sort_order == "asc" else column.desc()
        statement = (
            select(Product)
            .options(joinedload(Product.category))
            .join(Category, Product.category_id == Category.id)
            .where(*filters)
            .order_by(column, Product.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(db.scalars(statement)), total

    def get(self, db: Session, product_id: int) -> Product | None:
        return db.scalar(
            select(Product).options(joinedload(Product.category)).where(Product.id == product_id)
        )

    def update(self, db: Session, product: Product, data: ProductCreate | ProductUpdate) -> Product:
        values = data.model_dump(exclude_unset=True)
        for field in ("category_id", "name", "sku", "price", "stock_quantity"):
            if field in values and values[field] is None:
                raise ValueError(f"{field} cannot be null.")
        if "category_id" in values:
            category = db.get(Category, values["category_id"])
            if category is None or not category.is_active:
                raise ValueError("Category does not exist or is inactive.")

        product = db.scalar(select(Product).where(Product.id == product.id).with_for_update())
        if product is None:
            raise ValueError("Product not found.")
        resulting_price = values.get("price", product.price)
        resulting_discount = values.get("discount_price", product.discount_price)
        if resulting_discount is not None and resulting_discount > resulting_price:
            raise ValueError("Discount price cannot exceed product price.")

        new_stock = values.pop("stock_quantity", product.stock_quantity)
        previous_stock = product.stock_quantity
        for field, value in values.items():
            if field == "image_url":
                value = str(value) if value is not None else None
            setattr(product, field, value)
        product.stock_quantity = new_stock

        try:
            if new_stock != previous_stock:
                db.add(
                    InventoryTransaction(
                        product_id=product.id,
                        transaction_type="IN" if new_stock > previous_stock else "OUT",
                        quantity=abs(new_stock - previous_stock),
                        previous_stock=previous_stock,
                        updated_stock=new_stock,
                        remarks="Stock changed through product update",
                    )
                )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        db.refresh(product)
        return product

    def deactivate(self, db: Session, product: Product) -> None:
        product.is_active = False
        self._commit(db)

    @staticmethod
    def _commit(db: Session) -> None:
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise


product_service = ProductService()
