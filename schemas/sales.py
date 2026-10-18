"""销售模块 Schema。

包含销售订单与销售出库单的 Create / Update / Response 系列。
- Create 类只包含前端传入字段，不含 server 生成字段（id/order_no/status/金额汇总等）。
- 明细 amount、头 total_quantity / total_amount 由 server 计算。
- 金额类字段对齐 Numeric(12,2)。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from . import _BaseSchema


# ===========================================================================
# 销售订单
# ===========================================================================


class SalesOrderItemCreate(_BaseSchema):
    """销售订单明细创建请求体。"""

    product_id: int = Field(..., description="商品ID")
    quantity: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, description="订购数量（必须大于0）"
    )
    unit_price: Decimal = Field(
        ..., ge=0, max_digits=12, decimal_places=2, description="单价（必须大于等于0）"
    )
    remark: str | None = Field(default=None, max_length=255, description="备注")


class SalesOrderCreate(_BaseSchema):
    """销售订单创建请求体。"""

    customer_id: int = Field(..., description="客户ID")
    warehouse_id: int = Field(..., description="出库仓库ID")
    remark: str | None = Field(default=None, max_length=255, description="备注")
    items: list[SalesOrderItemCreate] = Field(
        ..., min_length=1, description="订单明细列表（至少一条）"
    )


class SalesOrderUpdate(_BaseSchema):
    """销售订单更新请求体（全量替换明细）。"""

    customer_id: int = Field(..., description="客户ID")
    warehouse_id: int = Field(..., description="出库仓库ID")
    remark: str | None = Field(default=None, max_length=255, description="备注")
    items: list[SalesOrderItemCreate] = Field(
        ..., min_length=1, description="订单明细列表（全量替换，至少一条）"
    )


class SalesOrderItemOut(_BaseSchema):
    """销售订单明细响应体。"""

    id: int
    sales_order_id: int
    product_id: int
    quantity: Decimal = Field(max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    shipped_quantity: Decimal = Field(max_digits=12, decimal_places=2)
    remark: str | None
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    product_name: str = Field(default="", description="商品名称")
    product_sku: str = Field(default="", description="商品编码")


class SalesOrderResponse(_BaseSchema):
    """销售订单响应体（含明细列表）。"""

    id: int
    order_no: str
    customer_id: int
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
    customer_name: str = Field(default="", description="客户名称")
    warehouse_name: str = Field(default="", description="仓库名称")
    items: list[SalesOrderItemOut] = Field(default_factory=list, description="订单明细")


# ===========================================================================
# 销售出库单
# ===========================================================================


class SalesOutItemCreate(_BaseSchema):
    """销售出库单明细创建请求体。"""

    sales_order_item_id: int = Field(..., description="关联销售订单明细ID")
    quantity: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, description="本次出库数量（必须大于0）"
    )
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2, description="单价（不传则取订单明细单价）"
    )
    batch_no: str | None = Field(default=None, max_length=64, description="批次号")
    remark: str | None = Field(default=None, max_length=255, description="备注")


class SalesOutCreate(_BaseSchema):
    """销售出库单创建请求体。"""

    items: list[SalesOutItemCreate] = Field(
        ..., min_length=1, description="出库明细列表（至少一条）"
    )


class SalesOutItemOut(_BaseSchema):
    """销售出库单明细响应体。"""

    id: int
    sales_out_id: int
    sales_order_item_id: int
    product_id: int
    quantity: Decimal = Field(max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    batch_no: str | None
    remark: str | None
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    product_name: str = Field(default="", description="商品名称")
    product_sku: str = Field(default="", description="商品编码")


class SalesOutResponse(_BaseSchema):
    """销售出库单响应体（含明细列表）。"""

    id: int
    out_no: str
    sales_order_id: int
    customer_id: int
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
    customer_name: str = Field(default="", description="客户名称")
    warehouse_name: str = Field(default="", description="仓库名称")
    order_no: str = Field(default="", description="关联订单号")
    items: list[SalesOutItemOut] = Field(default_factory=list, description="出库明细")
