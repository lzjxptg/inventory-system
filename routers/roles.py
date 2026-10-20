"""角色与权限管理路由。

提供角色 CRUD、权限列表、角色权限分配、用户角色分配、
当前用户信息与权限查询接口。
响应统一用 success()/error() 包装。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.permissions import require_role
from core.response import error, success
from crud.role import (
    assign_role_permissions,
    create_role,
    delete_role,
    get_permission_codes_by_role_id,
    get_role,
    get_role_by_name,
    get_role_permission_ids,
    list_permissions,
    list_roles,
    update_role,
)
from crud.user import assign_user_role, list_users
from models.user import User
from schemas.role import (
    PermissionOut,
    RoleCreate,
    RolePermissionAssign,
    RoleResponse,
    RoleUpdate,
    UserRoleAssign,
)
from schemas.user import UserOut

router = APIRouter(prefix="/api/v1", tags=["权限管理"])


@router.get("/roles")
def list_roles_api(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """角色列表。"""
    items = list_roles(db, skip=skip, limit=limit)
    return success(
        data=[RoleResponse.model_validate(i).model_dump() for i in items]
    )


@router.post("/roles", dependencies=[Depends(require_role("admin"))])
def create_role_api(role_in: RoleCreate, db: Session = Depends(get_db)):
    """新建角色（仅 admin）。"""
    item = create_role(db, role_in)
    return success(
        data=RoleResponse.model_validate(item).model_dump(),
        msg="创建成功",
    )


@router.put("/roles/{role_id}", dependencies=[Depends(require_role("admin"))])
def update_role_api(
    role_id: int, role_in: RoleUpdate, db: Session = Depends(get_db)
):
    """更新角色（仅 admin）。"""
    item = update_role(db, role_id, role_in)
    if item is None:
        return error(code=404, msg="角色不存在")
    return success(
        data=RoleResponse.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/roles/{role_id}", dependencies=[Depends(require_role("admin"))])
def delete_role_api(role_id: int, db: Session = Depends(get_db)):
    """逻辑删除角色（仅 admin）。"""
    ok = delete_role(db, role_id)
    if not ok:
        return error(code=404, msg="角色不存在")
    return success(msg="删除成功")


@router.get("/permissions")
def list_permissions_api(db: Session = Depends(get_db)):
    """全部权限列表。"""
    items = list_permissions(db)
    return success(
        data=[PermissionOut.model_validate(i).model_dump() for i in items]
    )


@router.get("/roles/me")
def get_current_user_info(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """返回当前登录用户信息（含 role）。"""
    data = UserOut.model_validate(user).model_dump()
    if user.role_id is None:
        data["role"] = "operator"
    else:
        role = get_role(db, user.role_id)
        data["role"] = role.name if role else "operator"
    return success(data=data)


@router.get("/roles/me/permissions")
def get_my_permissions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """返回当前用户权限 code 列表。"""
    role_id = user.role_id
    if role_id is None:
        role = get_role_by_name(db, "operator")
        role_id = role.id if role else None
    if role_id is None:
        return success(data=[])
    codes = get_permission_codes_by_role_id(db, role_id)
    return success(data=codes)


@router.get("/roles/{role_id}/permissions")
def get_role_permissions_api(role_id: int, db: Session = Depends(get_db)):
    """查询角色已分配权限 ID 列表。"""
    if get_role(db, role_id) is None:
        return error(code=404, msg="角色不存在")
    ids = get_role_permission_ids(db, role_id)
    return success(data=ids)


@router.put(
    "/roles/{role_id}/permissions",
    dependencies=[Depends(require_role("admin"))],
)
def assign_role_permissions_api(
    role_id: int, body: RolePermissionAssign, db: Session = Depends(get_db)
):
    """分配角色权限（仅 admin，全量覆盖）。"""
    assign_role_permissions(db, role_id, body.permission_ids)
    return success(msg="权限分配成功")


@router.put("/users/{user_id}/role", dependencies=[Depends(require_role("admin"))])
def assign_user_role_api(
    user_id: int, body: UserRoleAssign, db: Session = Depends(get_db)
):
    """分配用户角色（仅 admin）。"""
    if get_role(db, body.role_id) is None:
        return error(code=400, msg="角色不存在")
    user = assign_user_role(db, user_id, body.role_id)
    if user is None:
        return error(code=404, msg="用户不存在")
    return success(
        data=UserOut.model_validate(user).model_dump(),
        msg="角色分配成功",
    )


@router.get("/users")
def list_users_api(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """用户列表（用于角色分配页面）。"""
    items = list_users(db, skip=skip, limit=limit)
    return success(
        data=[UserOut.model_validate(i).model_dump() for i in items]
    )
