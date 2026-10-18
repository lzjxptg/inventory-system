"""计量单位 Schema。

包含 Create / Update / Response 三类。
name 为唯一字段，code 可空；sort、is_deleted 在 Create 中给出与
server_default 一致的默认值。
"""

from datetime import datetime

from pydantic import Field

from . import _BaseSchema


class UnitCreate(_BaseSchema):
    """新增单位请求体。"""

    name: str = Field(..., max_length=20, description="单位名称（个/箱/件/包）")
    code: str | None = Field(default=None, max_length=20, description="单位编码")
    sort: int = Field(default=0, ge=0, description="排序")
    is_deleted: int = Field(
        default=0, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class UnitUpdate(_BaseSchema):
    """编辑单位请求体，字段全部可选。"""

    name: str | None = Field(default=None, max_length=20, description="单位名称")
    code: str | None = Field(default=None, max_length=20, description="单位编码")
    sort: int | None = Field(default=None, ge=0, description="排序")
    is_deleted: int | None = Field(
        default=None, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class UnitResponse(_BaseSchema):
    """单位响应体。"""

    id: int
    name: str
    code: str | None
    sort: int
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    created_at: datetime
