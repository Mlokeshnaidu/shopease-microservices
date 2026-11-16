"""Transactional inventory operations with a persistent stock audit trail."""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory_model import InventoryTransaction
from app.models.inventory_reservation_model import InventoryReservation
from app.models.product_model import Product
from app.schemas.inventory_schema import InventoryReservationCreate, StockAdjustment


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

    def reserve_for_order(
        self,
        db: Session,
        reservation: InventoryReservationCreate,
    ) -> tuple[str, bool]:
        requested: dict[int, int] = {}
        for item in reservation.items:
            requested[item.product_id] = requested.get(item.product_id, 0) + item.quantity
        if any(quantity > 10000 for quantity in requested.values()):
            raise ValueError("Combined product quantity must not exceed 10000.")

        try:
            products: dict[int, Product] = {}
            for product_id in sorted(requested):
                product = db.scalar(
                    select(Product)
                    .where(Product.id == product_id)
                    .with_for_update()
                )
                if product is None:
                    db.rollback()
                    raise LookupError(f"Product {product_id} not found.")
                if not product.is_active or not product.category.is_active:
                    db.rollback()
                    raise ValueError(f"Product {product_id} is inactive.")
                products[product_id] = product

            existing = list(
                db.scalars(
                    select(InventoryReservation)
                    .where(InventoryReservation.order_ref == reservation.order_ref)
                    .with_for_update()
                )
            )
            if existing:
                existing_items = {item.product_id: item.quantity for item in existing}
                if existing_items != requested:
                    db.rollback()
                    raise ValueError("Order reference was already used for a different reservation.")
                if any(item.status != "RESERVED" for item in existing):
                    db.rollback()
                    raise ValueError("Released inventory cannot be reserved again for this order.")
                db.rollback()
                return "RESERVED", True

            for product_id, quantity in requested.items():
                product = products[product_id]
                if product.stock_quantity < quantity:
                    db.rollback()
                    raise ValueError(f"Insufficient stock for product {product_id}.")

            for product_id, quantity in requested.items():
                product = products[product_id]
                previous_stock = product.stock_quantity
                product.stock_quantity -= quantity
                db.add(
                    InventoryTransaction(
                        product_id=product_id,
                        transaction_type="OUT",
                        quantity=quantity,
                        previous_stock=previous_stock,
                        updated_stock=product.stock_quantity,
                        remarks=f"Order reservation {reservation.order_ref}",
                    )
                )
                db.add(
                    InventoryReservation(
                        order_ref=reservation.order_ref,
                        product_id=product_id,
                        quantity=quantity,
                        status="RESERVED",
                    )
                )
            db.commit()
            return "RESERVED", False
        except SQLAlchemyError:
            db.rollback()
            raise

    def release_for_order(self, db: Session, order_ref: str) -> tuple[str, list[InventoryReservation], bool]:
        try:
            order_reservations = list(
                db.scalars(
                    select(InventoryReservation)
                    .where(InventoryReservation.order_ref == order_ref)
                    .order_by(InventoryReservation.product_id)
                )
            )
            if not order_reservations:
                db.rollback()
                raise LookupError("Inventory reservation not found.")

            products: dict[int, Product] = {}
            for product_id in sorted(item.product_id for item in order_reservations):
                product = db.scalar(
                    select(Product)
                    .where(Product.id == product_id)
                    .with_for_update()
                )
                if product is None:
                    db.rollback()
                    raise LookupError(f"Product {product_id} not found.")
                products[product_id] = product

            reservations = list(
                db.scalars(
                    select(InventoryReservation)
                    .where(InventoryReservation.order_ref == order_ref)
                    .order_by(InventoryReservation.product_id)
                    .with_for_update()
                )
            )
            if all(item.status == "RELEASED" for item in reservations):
                db.rollback()
                return "RELEASED", reservations, True
            if any(item.status != "RESERVED" for item in reservations):
                db.rollback()
                raise ValueError("Inventory reservation has an inconsistent state.")

            for reservation in reservations:
                product = products[reservation.product_id]
                previous_stock = product.stock_quantity
                product.stock_quantity += reservation.quantity
                reservation.status = "RELEASED"
                db.add(
                    InventoryTransaction(
                        product_id=product.id,
                        transaction_type="IN",
                        quantity=reservation.quantity,
                        previous_stock=previous_stock,
                        updated_stock=product.stock_quantity,
                        remarks=f"Order cancellation {order_ref}",
                    )
                )
            db.commit()
            return "RELEASED", reservations, False
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
