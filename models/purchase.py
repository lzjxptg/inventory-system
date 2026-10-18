"""采购模块表结构。

包含四张表：
- purchase_orders：采购订单头
- purchase_order_items：采购订单明细
- purchase_ins：采购入库单头
- purchase_in_items：采购入库单明细

订单管"计划"，入库单管"执行"，入库单通过 purchase_order_id 关联订单。
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


class PurchaseOrder(Base, CommonMixin):
    """采购订单头。"""

    __tablename__ = "purchase_orders"

    order_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="订单号，格式 PO-YYYYMMDD-序号"
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
        comment="收货仓库ID",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="draft",
        comment="状态：draft/submitted/approved/partial_in/received/completed/cancelled",
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
        ForeignKey("users.id", ondelete="RESTRICT"),
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

    # 关联对象，响应层取名称
    supplier = relationship("Supplier", lazy="select")
    warehouse = relationship("Warehouse", lazy="select")
    creator = relationship("User", foreign_keys=[created_by], lazy="select")
    approver = relationship("User", foreign_keys=[approved_by], lazy="select")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        "PurchaseOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("order_no", name="uq_purchase_orders_order_no"),
        Index("ix_purchase_orders_supplier_id", "supplier_id"),
        Index("ix_purchase_orders_status", "status"),
        Index("ix_purchase_orders_warehouse_id", "warehouse_id"),
        {"comment": "采购订单头表"},
    )

    @property
    def supplier_name(self) -> str:
        return self.supplier.name if self.supplier is not None else ""

    @property
    def warehouse_name(self) -> str:
        return self.warehouse.name if self.warehouse is not None else ""


class PurchaseOrderItem(Base, CommonMixin):
    """采购订单明细。"""

    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        comment="采购订单ID",
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
    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default="0.00",
        comment="已入库数量",
    )
    remark: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="备注"
    )

    order: Mapped["PurchaseOrder"] = relationship(
        "PurchaseOrder", back_populates="items"
    )
    product = relationship("Product", lazy="select")

    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id", "product_id", name="uq_po_item_order_product"
        ),
        Index("ix_purchase_order_items_product_id", "product_id"),
        Index("ix_purchase_order_items_order_id", "purchase_order_id"),
        {"comment": "采购订单明细表"},
    )

    @property
    def product_name(self) -> str:
        return self.product.name if self.product is not None else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product is not None else ""


class PurchaseIn(Base, CommonMixin):
    """采购入库单头。"""

    __tablename__ = "purchase_ins"

    in_no: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="入库单号，格式 PI-YYYYMMDD-序号"
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
        comment="入库仓库ID",
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
        ForeignKey("users.id", ondelete="RESTRICT"),
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

    supplier = relationship("Supplier", lazy="select")
    warehouse = relationship("Warehouse", lazy="select")
    creator = relationship("User", foreign_keys=[created_by], lazy="select")
    confirmer = relationship("User", foreign_keys=[confirmed_by], lazy="select")
    order = relationship("PurchaseOrder", lazy="select")
    items: Mapped[list["PurchaseInItem"]] = relationship(
        "PurchaseInItem",
        back_populates="purchase_in",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("in_no", name="uq_purchase_ins_in_no"),
        Index("ix_purchase_ins_order_id", "purchase_order_id"),
        Index("ix_purchase_ins_status", "status"),
        {"comment": "采购入库单头表"},
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


class PurchaseInItem(Base, CommonMixin):
    """采购入库单明细。"""

    __tablename__ = "purchase_in_items"

    purchase_in_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_ins.id", ondelete="CASCADE"),
        nullable=False,
        comment="采购入库单ID",
    )
    purchase_order_item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchase_order_items.id", ondelete="RESTRICT"),
        nullable=False,
        comment="关联采购订单明细ID",
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        comment="商品ID",
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, comment="本次入库数量"
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

    purchase_in: Mapped["PurchaseIn"] = relationship(
        "PurchaseIn", back_populates="items"
    )
    product = relationship("Product", lazy="select")
    order_item = relationship("PurchaseOrderItem", lazy="select")

    __table_args__ = (
        UniqueConstraint(
            "purchase_in_id", "product_id", name="uq_pi_item_in_product"
        ),
        Index("ix_purchase_in_items_product_id", "product_id"),
        Index("ix_purchase_in_items_in_id", "purchase_in_id"),
        {"comment": "采购入库单明细表"},
    )

    @property
    def product_name(self) -> str:
        return self.product.name if self.product is not None else ""

    @property
    def product_sku(self) -> str:
        return self.product.sku if self.product is not None else ""
