"""仓库 Schema。

包含 Create / Update / Response 三类。
is_deleted 在 Create 中给出与 server_default 一致的默认值。
"""

from datetime import datetime

from pydantic import Field

from . import _BaseSchema


class WarehouseCreate(_BaseSchema):
    """新增仓库请求体。"""

    code: str = Field(..., max_length=50, description="仓库编码，唯一")
    name: str = Field(..., max_length=100, description="仓库名称")
    manager: str | None = Field(default=None, max_length=50, description="负责人")
    is_deleted: int = Field(
        default=0, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class WarehouseUpdate(_BaseSchema):
    """编辑仓库请求体，字段全部可选。"""

    code: str | None = Field(default=None, max_length=50, description="仓库编码，唯一")
    name: str | None = Field(default=None, max_length=100, description="仓库名称")
    manager: str | None = Field(default=None, max_length=50, description="负责人")
    is_deleted: int | None = Field(
        default=None, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class WarehouseResponse(_BaseSchema):
    """仓库响应体。"""

    id: int
    code: str
    name: str
    manager: str | None
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    created_at: datetime
