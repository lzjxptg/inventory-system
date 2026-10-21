"""销售模块表结构。

包含四张表：
- sales_orders：销售订单头
- sales_order_items：销售订单明细
- sales_outs：销售出库单头
- sales_out_items：销售出库单明细

订单管"计划"，出库单管"执行"，出库单通过 sales_order_id 关联订单。
所有表继承 CommonMixin（id / is_deleted / created_at）。

外键 ondelete 策略：
- sales_order_items.sales_order_id 与 sales_out_items.sales_out_id 为 CASCADE（随头删除）。
- 其余外键为 RESTRICT。
- 【修正项】sales_orders.approved_by 与 sales_outs.confirmed_by → users.id 采用 SET NULL，
  原因：操作人用户被删除时已审核/已确认的单据应保留，只置空操作人字段，
  避免 RESTRICT 导致无法删除已产生业务单据的用户。
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


class SalesOrder(Base, CommonMixin):
    """销售订单头。"""

    __tablename__ = "sales_orders"

    order_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="订单号，格式 SO-YYYYMMDD-序号"
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
        comment="出库仓库ID",
    )
    shop_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("customer_shops.id", ondelete="SET NULL"),
        nullable=True,
        comment="收货门店ID，NULL 表示不指定具体门店",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="draft",
        comment="状态：draft/submitted/approved/partial_out/completed/cancelled",
    )
    total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="总数量",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="总金额",
    )
    remark: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="备注"
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="创建人ID",
    )
    approved_by: Mapped[int | None] = mapped_column(
        BigInteger,
        # 【修正项】SET NULL：操作人删除后置空，单据保留
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核人ID",
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
    shop = relationship("CustomerShop", lazy="select")
    creator = relationship("User", foreign_keys=[created_by], lazy="select")
    approver = relationship("User", foreign_keys=[approved_by], lazy="select")
    items: Mapped[list["SalesOrderItem"]] = relationship(
        "SalesOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("order_no", name="uq_sales_orders_order_no"),
        Index("ix_sales_orders_customer_id", "customer_id"),
        Index("ix_sales_orders_status", "status"),
        Index("ix_sales_orders_warehouse_id", "warehouse_id"),
        Index("ix_sales_orders_shop_id", "shop_id"),
        {"comment": "销售订单头表"},
    )

    @property
    def customer_name(self) -> str:
        return self.customer.name if self.customer is not None else ""

    @property
    def warehouse_name(self) -> str:
        return self.warehouse.name if self.warehouse is not None else ""

    @property
    def shop_name(self) -> str:
        return self.shop.shop_name if self.shop is not None else ""

    @property
    def shop_address(self) -> str:
        if self.shop is None or self.shop.address is None:
            return ""
        return self.shop.address


class SalesOrderItem(Base, CommonMixin):
    """销售订单明细。"""

    __tablename__ = "sales_order_items"

    sales_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
        comment="销售订单ID",
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="商品ID",
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="订购数量"
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="单价"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="金额 = quantity * unit_price"
    )
    shipped_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="已出库数量",
    )
    remark: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="备注"
    )

    order: Mapped["SalesOrder"] = relationship(
        "SalesOrder", back_populates="items"
    )
    product = relationship("Product", lazy="select")

    __table_args__ = (
        UniqueConstraint(
            "sales_order_id", "product_id", name="uq_soi_order_product"
        ),
        Index("ix_soi_product_id", "product_id"),
        Index("ix_soi_order_id", "sales_order_id"),
        {"comment": "销售订单明细表"},
    )

    @property
    def product_name(self) -> str:
        return self.product.name if self.product is not None else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product is not None else ""


class SalesOut(Base, CommonMixin):
    """销售出库单头。"""

    __tablename__ = "sales_outs"

    out_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="出库单号，格式 SOUT-YYYYMMDD-序号"
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
        comment="出库仓库ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="draft",
        comment="状态：draft/confirmed/cancelled",
    )
    total_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="总数量",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="总金额",
    )
    remark: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="备注"
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="创建人ID",
    )
    confirmed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        # 【修正项】SET NULL：操作人删除后置空，单据保留
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="确认人ID",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="确认时间"
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
    confirmer = relationship("User", foreign_keys=[confirmed_by], lazy="select")
    order = relationship("SalesOrder", lazy="select")
    items: Mapped[list["SalesOutItem"]] = relationship(
        "SalesOutItem",
        back_populates="sales_out",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("out_no", name="uq_sales_outs_out_no"),
        Index("ix_so_order_id", "sales_order_id"),
        Index("ix_so_status", "status"),
        {"comment": "销售出库单头表"},
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


class SalesOutItem(Base, CommonMixin):
    """销售出库单明细。"""

    __tablename__ = "sales_out_items"

    sales_out_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales_outs.id", ondelete="CASCADE"),
        nullable=False,
        comment="销售出库单ID",
    )
    sales_order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sales_order_items.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联销售订单明细ID",
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="商品ID",
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="本次出库数量"
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="单价"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="金额"
    )
    batch_no: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="批次号"
    )
    remark: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="备注"
    )

    sales_out: Mapped["SalesOut"] = relationship(
        "SalesOut", back_populates="items"
    )
    product = relationship("Product", lazy="select")
    order_item = relationship("SalesOrderItem", lazy="select")

    __table_args__ = (
        UniqueConstraint(
            "sales_out_id", "product_id", name="uq_soi_out_product"
        ),
        Index("ix_soi_out_product_id", "product_id"),
        Index("ix_soi_out_id", "sales_out_id"),
        {"comment": "销售出库单明细表"},
    )

    @property
    def product_name(self) -> str:
        return self.product.name if self.product is not None else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product is not None else ""
