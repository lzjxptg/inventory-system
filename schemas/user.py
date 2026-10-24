"""用户与鉴权相关 Schema。

- UserCreate：注册请求体（用户名 + 明文密码）。
- UserOut：用户响应体（不含密码/哈希）。
- Token：登录返回的 JWT 令牌。
"""

from datetime import datetime

from pydantic import Field

from . import _BaseSchema


class UserCreate(_BaseSchema):
    """注册请求体。"""

    username: str = Field(..., max_length=50, description="登录账号")
    password: str = Field(..., min_length=6, max_length=128, description="明文密码")
    role_id: int | None = Field(default=None, description="角色ID，NULL 默认 operator")


class UserOut(_BaseSchema):
    """用户响应体，不暴露密码哈希。"""

    id: int
    username: str
    is_active: bool
    role_id: int | None = None
    created_at: datetime


class UserUpdate(_BaseSchema):
    """编辑用户请求体。所有字段可选，仅提交的字段会被更新。"""

    username: str | None = Field(default=None, max_length=50, description="登录账号")
    password: str | None = Field(
        default=None, min_length=6, max_length=128, description="明文密码，留空则不修改"
    )
    role_id: int | None = Field(default=None, description="角色ID，NULL 默认 operator")


class ResetPassword(_BaseSchema):
    """重置密码请求体（admin 重置任意用户密码）。"""

    new_password: str = Field(..., min_length=6, max_length=128, description="新明文密码")


class Token(_BaseSchema):
    """登录返回的访问令牌。"""

    access_token: str
    token_type: str = Field(default="bearer", description="令牌类型，固定 bearer")
