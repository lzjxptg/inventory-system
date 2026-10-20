"""角色与权限 Schema。"""

from datetime import datetime

from pydantic import Field

from . import _BaseSchema


class RoleCreate(_BaseSchema):
    """新建角色请求体。"""

    name: str = Field(..., max_length=50, description="角色编码")
    description: str = Field(default="", max_length=255, description="角色描述")


class RoleUpdate(_BaseSchema):
    """编辑角色请求体。"""

    name: str | None = Field(default=None, max_length=50, description="角色编码")
    description: str | None = Field(default=None, max_length=255, description="角色描述")


class RoleResponse(_BaseSchema):
    """角色响应体。"""

    id: int
    name: str
    description: str
    is_deleted: int = Field(ge=0, le=1)
    created_at: datetime


class PermissionOut(_BaseSchema):
    """权限响应体。"""

    id: int
    code: str
    name: str
    module: str


class RolePermissionAssign(_BaseSchema):
    """角色权限分配请求体。"""

    permission_ids: list[int] = Field(..., description="权限ID列表")


class UserRoleAssign(_BaseSchema):
    """用户角色分配请求体。"""

    role_id: int = Field(..., description="角色ID")
