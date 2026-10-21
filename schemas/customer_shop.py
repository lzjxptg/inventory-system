"""客户门店 Schema。

包含 Create / Update / Response 三类。
同一客户下门店名称唯一（含 is_deleted 的复合唯一约束）。
"""

from datetime import datetime

from pydantic import Field

from . import _BaseSchema


class CustomerShopCreate(_BaseSchema):
    """新增门店请求体。"""

    customer_id: int = Field(..., description="所属客户ID")
    shop_name: str = Field(..., max_length=100, description="门店名称")
    contact: str | None = Field(default=None, max_length=50, description="联系人")
    phone: str | None = Field(default=None, max_length=20, description="电话")
    address: str | None = Field(default=None, max_length=200, description="收货地址")
    is_default: int = Field(default=0, ge=0, le=1, description="是否默认门店：0否 1是")


class CustomerShopUpdate(_BaseSchema):
    """编辑门店请求体，字段全部可选。"""

    shop_name: str | None = Field(default=None, max_length=100, description="门店名称")
    contact: str | None = Field(default=None, max_length=50, description="联系人")
    phone: str | None = Field(default=None, max_length=20, description="电话")
    address: str | None = Field(default=None, max_length=200, description="收货地址")
    is_default: int | None = Field(default=None, ge=0, le=1, description="是否默认门店")


class CustomerShopOut(_BaseSchema):
    """门店响应体。"""

    id: int
    customer_id: int
    shop_name: str
    contact: str | None
    phone: str | None
    address: str | None
    is_default: int = Field(ge=0, le=1, description="是否默认门店")
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除")
    created_at: datetime
