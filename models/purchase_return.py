"""采购退货模块表结构。

包含两张表：
- purchase_returns：采购退货单头
- purchase_return_items：采购退货单明细

退货单通过 purchase_order_id 关联原采购订单。
审核通过后，商品退回仓库 → 库存余额增加（IN 流水）。
所有表继承 CommonMixin（id / is_deleted / created_at）。
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


class PurchaseReturn(Base, CommonMixin):
    """采购退货单头。"""

    __tablename__ = "purchase_returns"

    return_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="退货单号，格式 PR-YYYYMMDD-序号"
    )
    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联采购订单ID",
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="供应商ID",
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="退货入库仓库ID",
    )
    return_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="退货日期",
    )
    total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="退货总数量",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="退货总金额",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="draft",
        comment="状态：draft/submitted/approved/rejected",
    )
    reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="退货原因"
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="创建人ID",
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核人ID",
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="审核时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    supplier = relationship("Supplier", lazy="select")
    warehouse = relationship("Warehouse", lazy="select")
    creator = relationship("User", foreign_keys=[created_by], lazy="select")
    approver = relationship("User", foreign_keys=[approved_by], lazy="select")
    order = relationship("PurchaseOrder", lazy="select")
    items: Mapped[list["PurchaseReturnItem"]] = relationship(
        "PurchaseReturnItem",
        back_populates="return_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("return_no", name="uq_purchase_returns_return_no"),
        Index("ix_purchase_returns_order_id", "purchase_order_id"),
        Index("ix_purchase_returns_status", "status"),
        Index("ix_purchase_returns_supplier_id", "supplier_id"),
        {"comment": "采购退货单头表"},
    )

    @property
    def supplier_name(self) -> str:
        return self.supplier.name if self.supplier is not None else ""

    @property
    def warehouse_name(self) -> str:
        return self.warehouse.name if self.warehouse is not None else ""

    @property
    def order_no(self) -> str:
        return self.order.order_no if self.order is not None else ""


class PurchaseReturnItem(Base, CommonMixin):
    """采购退货单明细。"""

    __tablename__ = "purchase_return_items"

    return_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_returns.id", ondelete="CASCADE"),
        nullable=False,
        comment="采购退货单ID",
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="商品ID",
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="退货数量"
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="退货单价"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="金额 = 数量 × 单价"
    )
    batch_no: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="批次号"
    )

    return_order: Mapped["PurchaseReturn"] = relationship(
        "PurchaseReturn", back_populates="items"
    )
    product = relationship("Product", lazy="select")

    __table_args__ = (
        UniqueConstraint("return_id", "product_id", name="uq_pri_return_product"),
        Index("ix_purchase_return_items_return_id", "return_id"),
        Index("ix_purchase_return_items_product_id", "product_id"),
        {"comment": "采购退货明细表"},
    )

    @property
    def product_name(self) -> str:
        return self.product.name if self.product is not None else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product is not None else ""
