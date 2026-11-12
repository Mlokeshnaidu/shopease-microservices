"""Database operations for product categories."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.category_model import Category
from app.models.product_model import Product
from app.schemas.category_schema import CategoryCreate, CategoryUpdate


class CategoryService:
    def create(self, db: Session, data: CategoryCreate) -> Category:
        category = Category(**data.model_dump())
        db.add(category)
        self._commit(db)
        db.refresh(category)
        return category

    def list(self, db: Session, include_inactive: bool = False) -> list[Category]:
        statement = select(Category).order_by(Category.name)
        if not include_inactive:
            statement = statement.where(Category.is_active.is_(True))
        return list(db.scalars(statement))

    def get(self, db: Session, category_id: int) -> Category | None:
        return db.get(Category, category_id)

    def update(self, db: Session, category: Category, data: CategoryUpdate) -> Category:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(category, field, value)
        self._commit(db)
        db.refresh(category)
        return category

    def delete(self, db: Session, category: Category) -> None:
        if db.scalar(select(Product.id).where(Product.category_id == category.id).limit(1)) is not None:
            raise ValueError("Category still has products. Reassign or deactivate those products before deleting it.")
        db.delete(category)
        self._commit(db)

    @staticmethod
    def _commit(db: Session) -> None:
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise


category_service = CategoryService()
