"""Add idempotent order inventory reservations.

Revision ID: 20261116_02
Revises: 20261112_01
Create Date: 2026-11-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261116_02"
down_revision: Union[str, None] = "20261112_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_ref", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity_positive"),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'RELEASED')",
            name="ck_inventory_reservation_status",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_ref",
            "product_id",
            name="uq_inventory_reservation_order_product",
        ),
    )
    op.create_index(
        "ix_inventory_reservations_order_ref",
        "inventory_reservations",
        ["order_ref"],
    )
    op.create_index(
        "ix_inventory_reservations_product_id",
        "inventory_reservations",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_reservations_product_id", table_name="inventory_reservations")
    op.drop_index("ix_inventory_reservations_order_ref", table_name="inventory_reservations")
    op.drop_table("inventory_reservations")
