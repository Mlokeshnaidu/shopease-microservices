"""Transactional inventory operations with a persistent stock audit trail."""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory_model import InventoryTransaction
from app.models.product_model import Product
from app.schemas.inventory_schema import StockAdjustment


class InventoryService:
    def get_stock(self, db: Session, product_id: int) -> Product | None:
        return db.get(Product, product_id)

    def adjust(
        self,
        db: Session,
        product_id: int,
        data: StockAdjustment,
        transaction_type: Literal["IN", "OUT"],
    ) -> Product | None:
        try:
            product = db.scalar(
                select(Product).where(Product.id == product_id).with_for_update()
            )
            if product is None:
                db.rollback()
                return None

            previous_stock = product.stock_quantity
            if transaction_type == "OUT" and data.quantity > previous_stock:
                db.rollback()
                raise ValueError("Insufficient stock for this stock-out operation.")

            updated_stock = (
                previous_stock + data.quantity
                if transaction_type == "IN"
                else previous_stock - data.quantity
            )
            product.stock_quantity = updated_stock
            db.add(
                InventoryTransaction(
                    product_id=product.id,
                    transaction_type=transaction_type,
                    quantity=data.quantity,
                    previous_stock=previous_stock,
                    updated_stock=updated_stock,
                    remarks=data.remarks,
                )
            )
            db.commit()
            db.refresh(product)
            return product
        except SQLAlchemyError:
            db.rollback()
            raise

    def history(self, db: Session, product_id: int) -> list[InventoryTransaction]:
        statement = (
            select(InventoryTransaction)
            .where(InventoryTransaction.product_id == product_id)
            .order_by(InventoryTransaction.created_at.desc(), InventoryTransaction.id.desc())
        )
        return list(db.scalars(statement))

    def low_stock(self, db: Session, threshold: int | None = None) -> list[Product]:
        effective_threshold = settings.low_stock_threshold if threshold is None else threshold
        statement = (
            select(Product)
            .where(Product.is_active.is_(True), Product.stock_quantity <= effective_threshold)
            .order_by(Product.stock_quantity, Product.id)
        )
        return list(db.scalars(statement))


inventory_service = InventoryService()
