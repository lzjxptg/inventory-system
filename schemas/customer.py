"""客户 Schema。

包含 Create / Update / Response 三类。
结构与 suppliers 表一致；phone 仅做长度校验（max_length=20），不做正则；
is_deleted 在 Create 中给出与 server_default 一致的默认值。
"""

from datetime import datetime

from pydantic import Field

from . import _BaseSchema


class CustomerCreate(_BaseSchema):
    """新增客户请求体。"""

    code: str = Field(..., max_length=50, description="客户编码，唯一")
    name: str = Field(..., max_length=200, description="客户名称")
    contact: str | None = Field(default=None, max_length=50, description="联系人")
    phone: str | None = Field(
        default=None, max_length=20, description="联系电话（仅长度校验，不做正则）"
    )
    address: str | None = Field(default=None, max_length=500, description="地址")
    is_deleted: int = Field(
        default=0, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class CustomerUpdate(_BaseSchema):
    """编辑客户请求体，字段全部可选。"""

    code: str | None = Field(default=None, max_length=50, description="客户编码，唯一")
    name: str | None = Field(default=None, max_length=200, description="客户名称")
    contact: str | None = Field(default=None, max_length=50, description="联系人")
    phone: str | None = Field(
        default=None, max_length=20, description="联系电话（仅长度校验，不做正则）"
    )
    address: str | None = Field(default=None, max_length=500, description="地址")
    is_deleted: int | None = Field(
        default=None, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class CustomerResponse(_BaseSchema):
    """客户响应体。"""

    id: int
    code: str
    name: str
    contact: str | None
    phone: str | None
    address: str | None
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    created_at: datetime
