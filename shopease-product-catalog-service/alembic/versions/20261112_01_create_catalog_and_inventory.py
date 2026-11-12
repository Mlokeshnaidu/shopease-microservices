"""Create product catalog, categories, and inventory history tables.

Revision ID: 20261112_01
Revises:
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261112_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_categories_name_not_blank"),
    )
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("brand", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price > 0", name="ck_products_price_positive"),
        sa.CheckConstraint(
            "discount_price IS NULL OR (discount_price > 0 AND discount_price <= price)",
            name="ck_products_discount_price",
        ),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_products_stock_nonnegative"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_products_name_not_blank"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)

    op.create_table(
        "inventory_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("previous_stock", sa.Integer(), nullable=False),
        sa.Column("updated_stock", sa.Integer(), nullable=False),
        sa.Column("remarks", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("transaction_type IN ('IN', 'OUT')", name="ck_inventory_transaction_type"),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_quantity_positive"),
        sa.CheckConstraint("previous_stock >= 0", name="ck_inventory_previous_stock_nonnegative"),
        sa.CheckConstraint("updated_stock >= 0", name="ck_inventory_updated_stock_nonnegative"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_inventory_transactions_product_id", "inventory_transactions", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_transactions_product_id", table_name="inventory_transactions")
    op.drop_table("inventory_transactions")
    op.drop_index("ix_products_sku", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_categories_name", table_name="categories")
    op.drop_table("categories")
