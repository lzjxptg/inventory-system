"""RBAC 权限模型：角色、权限、角色-权限关联。"""

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

from .base import CommonMixin


class Role(Base, CommonMixin):
    """角色表。"""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="角色编码"
    )
    description: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="角色描述"
    )

    __table_args__ = {"comment": "角色表"}

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions", lazy="selectin"
    )


class Permission(Base, CommonMixin):
    """权限表。"""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, comment="权限编码"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="权限名称"
    )
    module: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="所属模块"
    )

    __table_args__ = {"comment": "权限表"}


class RolePermission(Base, CommonMixin):
    """角色-权限关联表。"""

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id"), nullable=False, comment="角色ID"
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id"), nullable=False, comment="权限ID"
    )

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
        {"comment": "角色-权限关联表"},
    )
