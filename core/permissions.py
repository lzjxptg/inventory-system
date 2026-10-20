"""权限鉴权依赖。

基于 JWT payload 中的 ``role`` 字段做角色/权限校验。
- ``require_role(*roles)``：仅允许指定角色访问。
- ``require_permission(perm_code)``：校验当前用户是否拥有指定权限码。

用户角色为 NULL 时默认按 ``operator`` 处理。
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.exceptions import BusinessException
from crud.role import get_permission_codes_by_role_id, get_role_by_name
from models.user import User

DEFAULT_ROLE = "operator"


class ForbiddenException(BusinessException):
    """禁止访问，code=40301。"""

    def __init__(self, msg: str = "无权限访问"):
        super().__init__(code=40301, msg=msg)


def _get_user_role_name(user: User, db: Session) -> str:
    """获取用户角色 name。role_id 为 NULL 时返回默认 operator。"""
    if user.role_id is None:
        return DEFAULT_ROLE
    from models.role import Role
    from sqlalchemy import select

    stmt = select(Role.name).where(Role.id == user.role_id, Role.is_deleted == 0)
    name = db.execute(stmt).scalar_one_or_none()
    return name or DEFAULT_ROLE


def require_role(*roles: str):
    """角色校验依赖工厂。仅允许白名单角色访问。"""

    def _checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role_name = _get_user_role_name(user, db)
        if role_name not in roles:
            raise ForbiddenException(f"需要角色：{', '.join(roles)}")
        return user

    return _checker


def require_permission(perm_code: str):
    """权限码校验依赖工厂。用户角色需包含指定权限码。"""

    def _checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if user.role_id is None:
            # 默认 operator 角色，查其权限
            role = get_role_by_name(db, DEFAULT_ROLE)
            role_id = role.id if role else None
        else:
            role_id = user.role_id
        if role_id is None:
            raise ForbiddenException("用户无角色且默认角色不存在")
        codes = get_permission_codes_by_role_id(db, role_id)
        if perm_code not in codes:
            raise ForbiddenException(f"缺少权限：{perm_code}")
        return user

    return _checker
