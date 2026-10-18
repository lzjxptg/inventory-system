"""库存模块 Schema。

包含：
- StockMovementCreate：入库/出库请求体（movement_type 与 quantity 正负由路由层强制）。
- StockMovementOut：流水响应体，含商品/仓库/操作人名称。
- InventoryBalanceOut：余额响应体，含商品/仓库名称。
- InventoryAdjustRequest：盘点调整请求体（直接指定实际库存数量）。

数量类 Decimal 字段对齐 Numeric(10,2)。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from . import _BaseSchema


class StockMovementCreate(_BaseSchema):
    """库存流水创建请求体（入库/出库通用）。"""

    product_id: int = Field(..., description="商品ID")
    warehouse_id: int = Field(..., description="仓库ID")
    movement_type: str = Field(
        default="IN", max_length=20, description="流水类型：IN入库 OUT出库 ADJUST盘点调整（由路由层强制覆盖）"
    )
    quantity: Decimal = Field(
        ..., max_digits=10, decimal_places=2, description="变动数量：正数=入库，负数=出库"
    )
    reference_type: str | None = Field(
        default=None, max_length=50, description="关联单据类型：PURCHASE/SALE/ADJUST"
    )
    reference_id: int | None = Field(default=None, description="关联单据ID")
    remark: str | None = Field(default=None, max_length=255, description="备注")

    @model_validator(mode="after")
    def _validate_quantity_sign(self):
        """按 movement_type 校验数量正负：入库必须 > 0，出库必须 < 0。"""
        if self.movement_type == "IN" and self.quantity <= 0:
            raise ValueError("入库数量必须大于 0")
        if self.movement_type == "OUT" and self.quantity >= 0:
            raise ValueError("出库数量必须小于 0（传负数）")
        return self


class StockMovementOut(_BaseSchema):
    """库存流水响应体，含商品/仓库/操作人名称。"""

    id: int
    product_id: int
    warehouse_id: int
    movement_type: str
    quantity: Decimal = Field(max_digits=10, decimal_places=2)
    reference_type: str | None
    reference_id: int | None
    operator_id: int
    remark: str | None
    created_at: datetime
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    product_name: str = Field(default="", description="商品名称")
    warehouse_name: str = Field(default="", description="仓库名称")
    operator_name: str = Field(default="", description="操作人用户名")


class InventoryBalanceOut(_BaseSchema):
    """库存余额响应体，含商品/仓库名称。"""

    id: int
    product_id: int
    warehouse_id: int
    current_quantity: Decimal = Field(max_digits=10, decimal_places=2)
    product_name: str = Field(default="", description="商品名称")
    warehouse_name: str = Field(default="", description="仓库名称")
    updated_at: datetime


class InventoryAdjustRequest(_BaseSchema):
    """盘点调整请求体：直接指定实际库存数量。"""

    product_id: int = Field(..., description="商品ID")
    warehouse_id: int = Field(..., description="仓库ID")
    new_quantity: Decimal = Field(
        ..., max_digits=10, decimal_places=2, ge=0, description="盘点后的实际库存数量"
    )
    remark: str | None = Field(default=None, max_length=255, description="备注")
