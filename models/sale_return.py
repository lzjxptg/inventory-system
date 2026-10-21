"""销售退货模块表结构。

包含两张表：
- sales_returns：销售退货单头
- sales_return_items：销售退货单明细

退货单通过 sales_order_id 关联原销售订单。
审核通过后，商品从仓库出库（退回客户） → 库存余额扣减（OUT 流水）。
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


class SalesReturn(Base, CommonMixin):
    """销售退货单头。"""

    __tablename__ = "sales_returns"

    return_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="退货单号，格式 SR-YYYYMMDD-序号"
    )
    sales_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales_orders.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联销售订单ID",
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        comment="客户ID",
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        comment="退货出库仓库ID",
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

    customer = relationship("Customer", lazy="select")
    warehouse = relationship("Warehouse", lazy="select")
    creator = relationship("User", foreign_keys=[created_by], lazy="select")
    approver = relationship("User", foreign_keys=[approved_by], lazy="select")
    order = relationship("SalesOrder", lazy="select")
    items: Mapped[list["SalesReturnItem"]] = relationship(
        "SalesReturnItem",
        back_populates="return_order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("return_no", name="uq_sales_returns_return_no"),
        Index("ix_sales_returns_order_id", "sales_order_id"),
        Index("ix_sales_returns_status", "status"),
        Index("ix_sales_returns_customer_id", "customer_id"),
        {"comment": "销售退货单头表"},
    )

    @property
    def customer_name(self) -> str:
        return self.customer.name if self.customer is not None else ""

    @property
    def warehouse_name(self) -> str:
        return self.warehouse.name if self.warehouse is not None else ""

    @property
    def order_no(self) -> str:
        return self.order.order_no if self.order is not None else ""


class SalesReturnItem(Base, CommonMixin):
    """销售退货单明细。"""

    __tablename__ = "sales_return_items"

    return_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales_returns.id", ondelete="CASCADE"),
        nullable=False,
        comment="销售退货单ID",
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

    return_order: Mapped["SalesReturn"] = relationship(
        "SalesReturn", back_populates="items"
    )
    product = relationship("Product", lazy="select")

    __table_args__ = (
        UniqueConstraint("return_id", "product_id", name="uq_sri_return_product"),
        Index("ix_sales_return_items_return_id", "return_id"),
        Index("ix_sales_return_items_product_id", "product_id"),
        {"comment": "销售退货明细表"},
    )

    @property
    def product_name(self) -> str:
        return self.product.name if self.product is not None else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product is not None else ""
