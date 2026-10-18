"""报表模块 Schema。

定义库存流水汇总、低库存预警、采购/销售金额统计等报表接口的响应结构。
所有字段均为只读响应，不含创建/更新请求体。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from . import _BaseSchema


# ---------------------------------------------------------------------------
# 通用分页结构
# ---------------------------------------------------------------------------


class PageResult(_BaseSchema):
    """通用分页结果包装。"""

    items: list[dict[str, Any]] = Field(default_factory=list, description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")


# ---------------------------------------------------------------------------
# 接口 1：库存流水汇总
# ---------------------------------------------------------------------------


class MovementReportItem(_BaseSchema):
    """库存流水汇总单条记录。"""

    id: int
    product_id: int
    product_name: str = ""
    warehouse_id: int
    warehouse_name: str = ""
    movement_type: str
    quantity: Decimal
    reference_type: str | None = None
    reference_id: int | None = None
    remark: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# 接口 2：低库存预警
# ---------------------------------------------------------------------------


class LowStockAlertItem(_BaseSchema):
    """低库存预警单条记录。"""

    product_id: int
    product_name: str = ""
    warehouse_id: int
    warehouse_name: str = ""
    current_quantity: Decimal
    alert_threshold: Decimal = Field(..., description="预警阈值（取自商品 min_stock，缺省 10）")


# ---------------------------------------------------------------------------
# 接口 3：采购金额统计
# ---------------------------------------------------------------------------


class PurchaseBySupplierItem(_BaseSchema):
    """按供应商分组的采购统计。"""

    supplier_id: int
    supplier_name: str = ""
    order_count: int
    total_amount: Decimal


class PurchaseSummaryData(_BaseSchema):
    """采购金额统计结果。"""

    total_orders: int
    total_items: int
    total_amount: Decimal
    total_quantity: Decimal
    by_supplier: list[PurchaseBySupplierItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 接口 4：销售金额统计
# ---------------------------------------------------------------------------


class SalesByCustomerItem(_BaseSchema):
    """按客户分组的销售统计。"""

    customer_id: int
    customer_name: str = ""
    order_count: int
    total_amount: Decimal


class SalesSummaryData(_BaseSchema):
    """销售金额统计结果。"""

    total_orders: int
    total_items: int
    total_amount: Decimal
    total_quantity: Decimal
    by_customer: list[SalesByCustomerItem] = Field(default_factory=list)
