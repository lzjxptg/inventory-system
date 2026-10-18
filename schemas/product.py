"""商品 Schema。

包含 Create / Update / Response 三类。
字段名与 models/product.py 严格对齐（sku / purchase_price / sale_price /
min_stock），以保证 from_attributes=True 能正确从 ORM 对象取值。
金额类字段对齐 Numeric(12,2)，数量类字段对齐 Numeric(12,3)。
"""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from . import _BaseSchema


class ProductCreate(_BaseSchema):
    """新增商品请求体。"""

    sku: str = Field(..., max_length=50, description="商品编码，唯一")
    name: str = Field(..., max_length=200, description="商品名称")
    category_id: int | None = Field(default=None, description="分类ID，可空")
    unit_id: int = Field(..., description="计量单位ID")
    spec: str | None = Field(default=None, max_length=200, description="规格型号")
    purchase_price: Decimal = Field(
        default=0, max_digits=12, decimal_places=2, ge=0, description="参考采购价"
    )
    sale_price: Decimal = Field(
        default=0, max_digits=12, decimal_places=2, ge=0, description="参考销售价"
    )
    min_stock: Decimal = Field(
        default=0, max_digits=12, decimal_places=3, ge=0, description="最低库存预警"
    )
    status: int = Field(default=1, ge=0, le=1, description="状态：1上架 0下架")
    is_deleted: int = Field(
        default=0, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class ProductUpdate(_BaseSchema):
    """编辑商品请求体，字段全部可选。"""

    sku: str | None = Field(default=None, max_length=50, description="商品编码，唯一")
    name: str | None = Field(default=None, max_length=200, description="商品名称")
    category_id: int | None = Field(default=None, description="分类ID，可空")
    unit_id: int | None = Field(default=None, description="计量单位ID")
    spec: str | None = Field(default=None, max_length=200, description="规格型号")
    purchase_price: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2, ge=0, description="参考采购价"
    )
    sale_price: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2, ge=0, description="参考销售价"
    )
    min_stock: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=3, ge=0, description="最低库存预警"
    )
    status: int | None = Field(default=None, ge=0, le=1, description="状态：1上架 0下架")
    is_deleted: int | None = Field(
        default=None, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class ProductResponse(_BaseSchema):
    """商品响应体。"""

    id: int
    sku: str
    name: str
    category_id: int | None
    unit_id: int
    spec: str | None
    purchase_price: Decimal = Field(max_digits=12, decimal_places=2)
    sale_price: Decimal = Field(max_digits=12, decimal_places=2)
    min_stock: Decimal = Field(max_digits=12, decimal_places=3)
    status: int = Field(ge=0, le=1, description="状态：1上架 0下架")
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    created_at: datetime
    updated_at: datetime
