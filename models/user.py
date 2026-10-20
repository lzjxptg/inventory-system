"""用户表。

用于登录鉴权，包含用户名、密码哈希、启用状态。
继承 CommonMixin 获取 id、is_deleted、created_at 公共字段。
"""

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

from .base import CommonMixin


class User(Base, CommonMixin):
    """系统用户。"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="登录账号"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希（bcrypt）"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用"
    )
    role_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("roles.id"), nullable=True, comment="角色ID"
    )

    __table_args__ = {"comment": "用户表"}
