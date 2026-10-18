"""采购模块 Schema。

包含采购订单与采购入库单的 Create / Update / Response 系列。
- Create 类只包含前端传入字段，不含 server 生成字段（id/order_no/status/金额汇总等）。
- 明细 amount、头 total_quantity / total_amount 由 server 计算。
- 金额类字段对齐 Numeric(12,2)。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from . import _BaseSchema


# ===========================================================================
# 采购订单
# ===========================================================================


class PurchaseOrderItemCreate(_BaseSchema):
    """采购订单明细创建请求体。"""

    product_id: int = Field(..., description="商品ID")
    quantity: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, description="订购数量（必须大于0）"
    )
    unit_price: Decimal = Field(
        ..., ge=0, max_digits=12, decimal_places=2, description="单价（必须大于等于0）"
    )
    remark: str | None = Field(default=None, max_length=255, description="备注")


class PurchaseOrderCreate(_BaseSchema):
    """采购订单创建请求体。"""

    supplier_id: int = Field(..., description="供应商ID")
    warehouse_id: int = Field(..., description="收货仓库ID")
    remark: str | None = Field(default=None, max_length=255, description="备注")
    items: list[PurchaseOrderItemCreate] = Field(
        ..., min_length=1, description="订单明细列表（至少一条）"
    )


class PurchaseOrderUpdate(_BaseSchema):
    """采购订单更新请求体（全量替换明细）。"""

    supplier_id: int = Field(..., description="供应商ID")
    warehouse_id: int = Field(..., description="收货仓库ID")
    remark: str | None = Field(default=None, max_length=255, description="备注")
    items: list[PurchaseOrderItemCreate] = Field(
        ..., min_length=1, description="订单明细列表（全量替换，至少一条）"
    )


class PurchaseOrderItemOut(_BaseSchema):
    """采购订单明细响应体。"""

    id: int
    purchase_order_id: int
    product_id: int
    quantity: Decimal = Field(max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    received_quantity: Decimal = Field(max_digits=12, decimal_places=2)
    remark: str | None
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    product_name: str = Field(default="", description="商品名称")
    product_sku: str = Field(default="", description="商品编码")


class PurchaseOrderResponse(_BaseSchema):
    """采购订单响应体（含明细列表）。"""

    id: int
    order_no: str
    supplier_id: int
    warehouse_id: int
    status: str
    total_quantity: Decimal = Field(max_digits=12, decimal_places=2)
    total_amount: Decimal = Field(max_digits=12, decimal_places=2)
    remark: str | None
    created_by: int
    approved_by: int | None
    created_at: datetime
    updated_at: datetime
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    supplier_name: str = Field(default="", description="供应商名称")
    warehouse_name: str = Field(default="", description="仓库名称")
    items: list[PurchaseOrderItemOut] = Field(default_factory=list, description="订单明细")


# ===========================================================================
# 采购入库单
# ===========================================================================


class PurchaseInItemCreate(_BaseSchema):
    """采购入库单明细创建请求体。"""

    purchase_order_item_id: int = Field(..., description="关联采购订单明细ID")
    quantity: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, description="本次入库数量（必须大于0）"
    )
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2, description="单价（不传则取订单明细单价）"
    )
    batch_no: str | None = Field(default=None, max_length=64, description="批次号")
    remark: str | None = Field(default=None, max_length=255, description="备注")


class PurchaseInCreate(_BaseSchema):
    """采购入库单创建请求体。"""

    items: list[PurchaseInItemCreate] = Field(
        ..., min_length=1, description="入库明细列表（至少一条）"
    )


class PurchaseInItemOut(_BaseSchema):
    """采购入库单明细响应体。"""

    id: int
    purchase_in_id: int
    purchase_order_item_id: int
    product_id: int
    quantity: Decimal = Field(max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    batch_no: str | None
    remark: str | None
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    product_name: str = Field(default="", description="商品名称")
    product_sku: str = Field(default="", description="商品编码")


class PurchaseInResponse(_BaseSchema):
    """采购入库单响应体（含明细列表）。"""

    id: int
    in_no: str
    purchase_order_id: int
    supplier_id: int
    warehouse_id: int
    status: str
    total_quantity: Decimal = Field(max_digits=12, decimal_places=2)
    total_amount: Decimal = Field(max_digits=12, decimal_places=2)
    remark: str | None
    created_by: int
    confirmed_by: int | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    supplier_name: str = Field(default="", description="供应商名称")
    warehouse_name: str = Field(default="", description="仓库名称")
    order_no: str = Field(default="", description="关联订单号")
    items: list[PurchaseInItemOut] = Field(default_factory=list, description="入库明细")
