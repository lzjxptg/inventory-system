"""用户管理路由。

提供创建用户、编辑用户、删除用户、重置密码、按角色统计用户数接口。
- 列表（GET /users）与角色分配（PUT /users/{id}/role）位于 roles.py；
- 本文件负责 POST /users、PUT /users/{id}、DELETE /users/{id}、
  PUT /users/{id}/reset-password、GET /users/count-by-role。
所有端点需登录鉴权，且仅限 admin 角色。
响应统一用 success()/error() 包装。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.exceptions import ConflictException, NotFoundException, ValidationException
from core.permissions import require_role
from core.response import success
from crud.role import get_role
from crud.user import (
    count_users_by_role,
    create_user,
    delete_user,
    get_user_by_username,
    update_user,
    update_user_password,
)
from models.user import User
from schemas.user import ResetPassword, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["用户管理"])


@router.post("", dependencies=[Depends(require_role("admin"))])
def create_user_api(
    user_in: UserCreate,
    db: Session = Depends(get_db),
):
    """创建用户（仅 admin）。

    用户名唯一；role_id 为 NULL 时默认 operator 角色。
    """
    if get_user_by_username(db, user_in.username) is not None:
        raise ConflictException(f"用户名 {user_in.username} 已存在")

    # 若指定了 role_id，校验角色存在
    if user_in.role_id is not None:
        if get_role(db, user_in.role_id) is None:
            raise ValidationException("指定的角色不存在")

    user = create_user(db, user_in)
    return success(
        data=UserOut.model_validate(user).model_dump(),
        msg="创建成功",
    )


@router.get("/count-by-role", dependencies=[Depends(require_role("admin"))])
def count_users_by_role_api(role_key: str, db: Session = Depends(get_db)):
    """统计指定角色的启用用户数量（仅 admin）。"""
    count = count_users_by_role(db, role_key)
    return success(data={"role_key": role_key, "count": count})


@router.put("/{user_id}", dependencies=[Depends(require_role("admin"))])
def update_user_api(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
):
    """更新用户信息（仅 admin）。

    可更新用户名、角色、密码（密码留空则不修改）。
    """
    user = update_user(db, user_id, user_in)
    if user is None:
        raise NotFoundException("用户不存在")
    return success(
        data=UserOut.model_validate(user).model_dump(),
        msg="更新成功",
    )


@router.delete("/{user_id}", dependencies=[Depends(require_role("admin"))])
def delete_user_api(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除用户（仅 admin，逻辑删除）。

    - 不允许删除自己
    - 不允许删除最后一个启用的 admin
    """
    delete_user(db, user_id, operator_id=current_user.id)
    return success(msg="删除成功")


@router.put("/{user_id}/reset-password", dependencies=[Depends(require_role("admin"))])
def reset_password_api(
    user_id: int,
    body: ResetPassword,
    db: Session = Depends(get_db),
):
    """重置用户密码（仅 admin）。"""
    user = update_user_password(db, user_id, body.new_password)
    if user is None:
        raise NotFoundException("用户不存在")
    return success(msg="密码重置成功")
