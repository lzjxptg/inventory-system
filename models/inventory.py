"""库存相关表：库存余额表与库存流水表。

- inventory_balances：同一商品在同一仓库只有一条余额记录（唯一约束）。
- stock_movements：记录每一次库存变动（入库 IN / 出库 OUT / 盘点调整 ADJUST）。

两张表均继承 CommonMixin（id / is_deleted / created_at），
并通过 relationship 关联 products / warehouses / users，便于响应层取名称。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

from .base import CommonMixin


class InventoryBalance(Base, CommonMixin):
    """库存余额表：同一商品在同一仓库只有一条记录。"""

    __tablename__ = "inventory_balances"

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="商品ID",
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="仓库ID",
    )
    current_quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        server_default="0.00",
        comment="当前库存数量",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    # 关联商品与仓库，响应层取名称
    product = relationship("Product", lazy="select")
    warehouse = relationship("Warehouse", lazy="select")

    __table_args__ = (
        UniqueConstraint(
            "product_id", "warehouse_id", name="uq_inventory_balances_product_warehouse"
        ),
        Index("ix_inventory_balances_product_id", "product_id"),
        Index("ix_inventory_balances_warehouse_id", "warehouse_id"),
        {"comment": "库存余额表"},
    )

    @property
    def product_name(self) -> str:
        """商品名称（供响应 schema 读取）。"""
        return self.product.name if self.product is not None else ""

    @property
    def warehouse_name(self) -> str:
        """仓库名称（供响应 schema 读取）。"""
        return self.warehouse.name if self.warehouse is not None else ""


class StockMovement(Base, CommonMixin):
    """库存流水表：记录每一次库存变动。"""

    __tablename__ = "stock_movements"

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="商品ID",
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="仓库ID",
    )
    movement_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="流水类型：IN入库 OUT出库 ADJUST盘点调整",
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="变动数量（正数增加库存，负数减少库存）",
    )
    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="关联单据类型：PURCHASE/SALE/ADJUST",
    )
    reference_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="关联单据ID",
    )
    operator_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="操作人ID",
    )
    remark: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="备注",
    )

    # 关联商品、仓库、操作人，响应层取名称
    product = relationship("Product", lazy="select")
    warehouse = relationship("Warehouse", lazy="select")
    operator = relationship("User", foreign_keys=[operator_id], lazy="select")

    __table_args__ = (
        Index("ix_stock_movements_product_id", "product_id"),
        Index("ix_stock_movements_warehouse_id", "warehouse_id"),
        Index("ix_stock_movements_created_at", "created_at"),
        Index("ix_stock_movements_operator_id", "operator_id"),
        {"comment": "库存流水表"},
    )

    @property
    def product_name(self) -> str:
        """商品名称（供响应 schema 读取）。"""
        return self.product.name if self.product is not None else ""

    @property
    def warehouse_name(self) -> str:
        """仓库名称（供响应 schema 读取）。"""
        return self.warehouse.name if self.warehouse is not None else ""

    @property
    def operator_name(self) -> str:
        """操作人用户名（供响应 schema 读取）。"""
        return self.operator.username if self.operator is not None else ""
