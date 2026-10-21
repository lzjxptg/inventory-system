"""修复逻辑删除后唯一约束冲突：products/units/suppliers/customers 的唯一索引加入 is_deleted

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-21

修复逻辑删除后重建相同编码报唯一约束冲突的问题。
原唯一索引只含业务字段，逻辑删除（is_deleted=1）的旧记录仍占用唯一值，
导致用相同编码重建时触发 DB 级唯一约束冲突（500 异常）。
改为业务字段 + is_deleted 的复合唯一索引，使已删除记录不再占用唯一值。
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # products: uq_products_sku (sku) -> (sku, is_deleted)
    op.drop_index("uq_products_sku", table_name="products")
    op.create_index("uq_products_sku", "products", ["sku", "is_deleted"], unique=True)

    # units: name (name) -> uq_units_name (name, is_deleted)
    op.drop_index("name", table_name="units")
    op.create_unique_constraint("uq_units_name", "units", ["name", "is_deleted"])

    # suppliers: code (code) -> uq_suppliers_code (code, is_deleted)
    op.drop_index("code", table_name="suppliers")
    op.create_unique_constraint("uq_suppliers_code", "suppliers", ["code", "is_deleted"])

    # customers: code (code) -> uq_customers_code (code, is_deleted)
    op.drop_index("code", table_name="customers")
    op.create_unique_constraint("uq_customers_code", "customers", ["code", "is_deleted"])


def downgrade() -> None:
    # customers
    op.drop_constraint("uq_customers_code", "customers", type_="unique")
    op.create_index("code", "customers", ["code"], unique=True)

    # suppliers
    op.drop_constraint("uq_suppliers_code", "suppliers", type_="unique")
    op.create_index("code", "suppliers", ["code"], unique=True)

    # units
    op.drop_constraint("uq_units_name", "units", type_="unique")
    op.create_index("name", "units", ["name"], unique=True)

    # products
    op.drop_index("uq_products_sku", table_name="products")
    op.create_index("uq_products_sku", "products", ["sku"], unique=True)
