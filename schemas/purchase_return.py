"""采购退货模块 Schema。

包含采购退货单的 Create / Update / Response 系列。
- Create 类只包含前端传入字段，不含 server 生成字段（id/return_no/status/金额汇总等）。
- 明细 amount、头 total_quantity / total_amount 由 server 计算。
- 金额类字段对齐 Numeric(12,2)。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from . import _BaseSchema


class PurchaseReturnItemCreate(_BaseSchema):
    """采购退货单明细创建请求体。"""

    product_id: int = Field(..., description="商品ID")
    quantity: Decimal = Field(
        ..., gt=0, max_digits=12, decimal_places=2, description="退货数量（必须大于0）"
    )
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2,
        description="退货单价（不传则取原采购订单明细单价）",
    )
    batch_no: str | None = Field(default=None, max_length=64, description="批次号")


class PurchaseReturnCreate(_BaseSchema):
    """采购退货单创建请求体。"""

    purchase_order_id: int = Field(..., description="关联采购订单ID")
    reason: str | None = Field(default=None, max_length=500, description="退货原因")
    items: list[PurchaseReturnItemCreate] = Field(
        ..., min_length=1, description="退货明细列表（至少一条）"
    )


class PurchaseReturnUpdate(_BaseSchema):
    """采购退货单更新请求体（仅 draft 可改，全量替换明细）。"""

    reason: str | None = Field(default=None, max_length=500, description="退货原因")
    items: list[PurchaseReturnItemCreate] = Field(
        ..., min_length=1, description="退货明细列表（全量替换，至少一条）"
    )


class PurchaseReturnItemOut(_BaseSchema):
    """采购退货单明细响应体。"""

    id: int
    return_id: int
    product_id: int
    quantity: Decimal = Field(max_digits=12, decimal_places=2)
    unit_price: Decimal = Field(max_digits=12, decimal_places=2)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    batch_no: str | None
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    product_name: str = Field(default="", description="商品名称")
    product_sku: str = Field(default="", description="商品编码")


class PurchaseReturnResponse(_BaseSchema):
    """采购退货单响应体（含明细列表）。"""

    id: int
    return_no: str
    purchase_order_id: int
    supplier_id: int
    warehouse_id: int
    return_date: datetime
    total_quantity: Decimal = Field(max_digits=12, decimal_places=2)
    total_amount: Decimal = Field(max_digits=12, decimal_places=2)
    status: str
    reason: str | None
    created_by: int
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    supplier_name: str = Field(default="", description="供应商名称")
    warehouse_name: str = Field(default="", description="仓库名称")
    order_no: str = Field(default="", description="关联采购订单号")
    items: list[PurchaseReturnItemOut] = Field(default_factory=list, description="退货明细")
