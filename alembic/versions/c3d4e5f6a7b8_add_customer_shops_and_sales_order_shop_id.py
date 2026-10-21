"""新增客户门店子表 + 销售订单 shop_id 字段

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-21

支持连锁客户多门店管理：
- 新建 customer_shops 表（客户下的收货门店）
- sales_orders 新增 shop_id 字段（可空，关联客户门店）
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新建 customer_shops 表
    op.create_table(
        "customer_shops",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False, comment="所属客户ID"),
        sa.Column("shop_name", sa.String(length=100), nullable=False, comment="门店名称"),
        sa.Column("contact", sa.String(length=50), nullable=True, comment="联系人"),
        sa.Column("phone", sa.String(length=20), nullable=True, comment="电话"),
        sa.Column("address", sa.String(length=200), nullable=True, comment="收货地址"),
        sa.Column(
            "is_default",
            mysql.TINYINT(),
            server_default="0",
            nullable=False,
            comment="是否默认门店：0否 1是",
        ),
        sa.Column(
            "is_deleted",
            mysql.TINYINT(),
            server_default="0",
            nullable=False,
            comment="逻辑删除：0正常 1已删除",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="更新时间",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id", "shop_name", "is_deleted", name="uq_cs_customer_shop_name"
        ),
        comment="客户门店表",
    )
    op.create_index("ix_customer_shops_customer_id", "customer_shops", ["customer_id"])

    # sales_orders 新增 shop_id
    op.add_column(
        "sales_orders",
        sa.Column(
            "shop_id",
            sa.BigInteger(),
            nullable=True,
            comment="收货门店ID，NULL 表示不指定具体门店",
        ),
    )
    op.create_foreign_key(
        "fk_sales_orders_shop_id",
        "sales_orders",
        "customer_shops",
        ["shop_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sales_orders_shop_id", "sales_orders", ["shop_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_orders_shop_id", table_name="sales_orders")
    op.drop_constraint("fk_sales_orders_shop_id", "sales_orders", type_="foreignkey")
    op.drop_column("sales_orders", "shop_id")

    op.drop_index("ix_customer_shops_customer_id", table_name="customer_shops")
    op.drop_table("customer_shops")
