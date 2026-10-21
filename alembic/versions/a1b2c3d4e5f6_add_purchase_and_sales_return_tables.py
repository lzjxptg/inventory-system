"""add_purchase_and_sales_return_tables

Revision ID: a1b2c3d4e5f6
Revises: 064d6b94f98e
Create Date: 2026-10-21 20:00:00.000000

新增采购退货与销售退货四张表：
- purchase_returns / purchase_return_items
- sales_returns / sales_return_items
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '064d6b94f98e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ===== 采购退货单头 =====
    op.create_table(
        'purchase_returns',
        sa.Column('return_no', sa.String(length=64), nullable=False, comment='退货单号，格式 PR-YYYYMMDD-序号'),
        sa.Column('purchase_order_id', sa.BigInteger(), nullable=False, comment='关联采购订单ID'),
        sa.Column('supplier_id', sa.BigInteger(), nullable=False, comment='供应商ID'),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False, comment='退货入库仓库ID'),
        sa.Column('return_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='退货日期'),
        sa.Column('total_quantity', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False, comment='退货总数量'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False, comment='退货总金额'),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False, comment='状态：draft/submitted/approved/rejected'),
        sa.Column('reason', sa.String(length=500), nullable=True, comment='退货原因'),
        sa.Column('created_by', sa.BigInteger(), nullable=False, comment='创建人ID'),
        sa.Column('approved_by', sa.BigInteger(), nullable=True, comment='审核人ID'),
        sa.Column('approved_at', sa.DateTime(), nullable=True, comment='审核时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('is_deleted', mysql.TINYINT(), server_default='0', nullable=False, comment='逻辑删除：0正常 1已删除'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('return_no', name='uq_purchase_returns_return_no'),
        comment='采购退货单头表',
    )
    op.create_index('ix_purchase_returns_order_id', 'purchase_returns', ['purchase_order_id'], unique=False)
    op.create_index('ix_purchase_returns_status', 'purchase_returns', ['status'], unique=False)
    op.create_index('ix_purchase_returns_supplier_id', 'purchase_returns', ['supplier_id'], unique=False)

    # ===== 采购退货明细 =====
    op.create_table(
        'purchase_return_items',
        sa.Column('return_id', sa.BigInteger(), nullable=False, comment='采购退货单ID'),
        sa.Column('product_id', sa.BigInteger(), nullable=False, comment='商品ID'),
        sa.Column('quantity', sa.Numeric(precision=12, scale=2), nullable=False, comment='退货数量'),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False, comment='退货单价'),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False, comment='金额 = 数量 × 单价'),
        sa.Column('batch_no', sa.String(length=64), nullable=True, comment='批次号'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('is_deleted', mysql.TINYINT(), server_default='0', nullable=False, comment='逻辑删除：0正常 1已删除'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['return_id'], ['purchase_returns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('return_id', 'product_id', name='uq_pri_return_product'),
        comment='采购退货明细表',
    )
    op.create_index('ix_purchase_return_items_return_id', 'purchase_return_items', ['return_id'], unique=False)
    op.create_index('ix_purchase_return_items_product_id', 'purchase_return_items', ['product_id'], unique=False)

    # ===== 销售退货单头 =====
    op.create_table(
        'sales_returns',
        sa.Column('return_no', sa.String(length=64), nullable=False, comment='退货单号，格式 SR-YYYYMMDD-序号'),
        sa.Column('sales_order_id', sa.BigInteger(), nullable=False, comment='关联销售订单ID'),
        sa.Column('customer_id', sa.BigInteger(), nullable=False, comment='客户ID'),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False, comment='退货出库仓库ID'),
        sa.Column('return_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='退货日期'),
        sa.Column('total_quantity', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False, comment='退货总数量'),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False, comment='退货总金额'),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False, comment='状态：draft/submitted/approved/rejected'),
        sa.Column('reason', sa.String(length=500), nullable=True, comment='退货原因'),
        sa.Column('created_by', sa.BigInteger(), nullable=False, comment='创建人ID'),
        sa.Column('approved_by', sa.BigInteger(), nullable=True, comment='审核人ID'),
        sa.Column('approved_at', sa.DateTime(), nullable=True, comment='审核时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('is_deleted', mysql.TINYINT(), server_default='0', nullable=False, comment='逻辑删除：0正常 1已删除'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('return_no', name='uq_sales_returns_return_no'),
        comment='销售退货单头表',
    )
    op.create_index('ix_sales_returns_order_id', 'sales_returns', ['sales_order_id'], unique=False)
    op.create_index('ix_sales_returns_status', 'sales_returns', ['status'], unique=False)
    op.create_index('ix_sales_returns_customer_id', 'sales_returns', ['customer_id'], unique=False)

    # ===== 销售退货明细 =====
    op.create_table(
        'sales_return_items',
        sa.Column('return_id', sa.BigInteger(), nullable=False, comment='销售退货单ID'),
        sa.Column('product_id', sa.BigInteger(), nullable=False, comment='商品ID'),
        sa.Column('quantity', sa.Numeric(precision=12, scale=2), nullable=False, comment='退货数量'),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False, comment='退货单价'),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False, comment='金额 = 数量 × 单价'),
        sa.Column('batch_no', sa.String(length=64), nullable=True, comment='批次号'),
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('is_deleted', mysql.TINYINT(), server_default='0', nullable=False, comment='逻辑删除：0正常 1已删除'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['return_id'], ['sales_returns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('return_id', 'product_id', name='uq_sri_return_product'),
        comment='销售退货明细表',
    )
    op.create_index('ix_sales_return_items_return_id', 'sales_return_items', ['return_id'], unique=False)
    op.create_index('ix_sales_return_items_product_id', 'sales_return_items', ['product_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_sales_return_items_product_id', table_name='sales_return_items')
    op.drop_index('ix_sales_return_items_return_id', table_name='sales_return_items')
    op.drop_table('sales_return_items')
    op.drop_index('ix_sales_returns_customer_id', table_name='sales_returns')
    op.drop_index('ix_sales_returns_status', table_name='sales_returns')
    op.drop_index('ix_sales_returns_order_id', table_name='sales_returns')
    op.drop_table('sales_returns')
    op.drop_index('ix_purchase_return_items_product_id', table_name='purchase_return_items')
    op.drop_index('ix_purchase_return_items_return_id', table_name='purchase_return_items')
    op.drop_table('purchase_return_items')
    op.drop_index('ix_purchase_returns_supplier_id', table_name='purchase_returns')
    op.drop_index('ix_purchase_returns_status', table_name='purchase_returns')
    op.drop_index('ix_purchase_returns_order_id', table_name='purchase_returns')
    op.drop_table('purchase_returns')
