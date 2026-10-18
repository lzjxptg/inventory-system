"""商品分类 Schema。

包含 Create / Update / Response 三类，以及树形结构用的 CategoryTreeNode。
is_deleted 使用 int + Field(ge=0, le=1)，不引入 Enum；
sort、is_deleted 在 Create 中给出与 server_default 一致的默认值。
"""

from datetime import datetime

from pydantic import Field

from . import _BaseSchema


class CategoryCreate(_BaseSchema):
    """新增分类请求体。"""

    name: str = Field(..., max_length=100, description="分类名称")
    parent_id: int | None = Field(default=None, description="父分类ID，None 为顶级")
    sort: int = Field(default=0, ge=0, description="排序")
    is_deleted: int = Field(
        default=0, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class CategoryUpdate(_BaseSchema):
    """编辑分类请求体，字段全部可选。"""

    name: str | None = Field(default=None, max_length=100, description="分类名称")
    parent_id: int | None = Field(default=None, description="父分类ID，None 为顶级")
    sort: int | None = Field(default=None, ge=0, description="排序")
    is_deleted: int | None = Field(
        default=None, ge=0, le=1, description="逻辑删除：0正常 1已删除"
    )


class CategoryResponse(_BaseSchema):
    """分类响应体。"""

    id: int
    name: str
    parent_id: int | None
    sort: int
    is_deleted: int = Field(ge=0, le=1, description="逻辑删除：0正常 1已删除")
    created_at: datetime


class CategoryTreeNode(_BaseSchema):
    """分类树节点，自引用 children。"""

    id: int
    name: str
    parent_id: int | None
    sort: int
    children: list["CategoryTreeNode"] = Field(default_factory=list, description="子分类")


# 自引用模型必须在定义后 rebuild，否则 Pydantic 无法解析前向引用
CategoryTreeNode.model_rebuild()
