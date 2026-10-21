"""RBAC 角色与权限预置数据 seed 脚本。

幂等：已存在的角色/权限会跳过，不重复插入。
所有操作在同一个事务中完成，出错自动回滚。

运行方式：
    .venv\\Scripts\\python.exe scripts/seed_roles.py
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，便于直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.database import SessionLocal
from models import Permission, Role, RolePermission, User


# 权限定义：(code, name, module)
PERMISSIONS = [
    # settings 模块
    ("role:manage", "角色管理", "settings"),
    ("user:role", "分配用户角色", "settings"),
    # purchase 模块
    ("purchase:view", "查看采购", "purchase"),
    ("purchase:create", "创建采购", "purchase"),
    ("purchase:delete", "删除采购", "purchase"),
    # sales 模块
    ("sales:view", "查看销售", "sales"),
    ("sales:create", "创建销售", "sales"),
    ("sales:delete", "删除销售", "sales"),
    # inventory 模块
    ("inventory:view", "查看库存", "inventory"),
    ("inventory:in", "入库操作", "inventory"),
    ("inventory:out", "出库操作", "inventory"),
    # purchase return 模块
    ("purchase_return:view", "查看采购退货", "purchase_return"),
    ("purchase_return:create", "创建采购退货", "purchase_return"),
    ("purchase_return:approve", "审核采购退货", "purchase_return"),
    # sales return 模块
    ("sales_return:view", "查看销售退货", "sales_return"),
    ("sales_return:create", "创建销售退货", "sales_return"),
    ("sales_return:approve", "审核销售退货", "sales_return"),
    # reports 模块
    ("reports:view", "查看报表", "reports"),
]

# 角色定义：name -> description
ROLES = {
    "admin": "超级管理员，拥有全部权限",
    "operator": "普通操作员，可查看与创建，无删除与配置权限",
}

# operator 角色拥有的权限 code 列表（不含 :delete、role:manage、user:role）
OPERATOR_PERMISSIONS = [
    "purchase:view",
    "purchase:create",
    "sales:view",
    "sales:create",
    "inventory:view",
    "inventory:in",
    "inventory:out",
    "purchase_return:view",
    "purchase_return:create",
    "sales_return:view",
    "sales_return:create",
    "reports:view",
]


def _get_or_create_permission(session, code: str, name: str, module: str) -> Permission:
    """幂等获取或创建权限。"""
    perm = session.execute(
        select(Permission).where(Permission.code == code)
    ).scalar_one_or_none()
    if perm is None:
        perm = Permission(code=code, name=name, module=module)
        session.add(perm)
        session.flush()
    return perm


def _get_or_create_role(session, name: str, description: str) -> Role:
    """幂等获取或创建角色。"""
    role = session.execute(
        select(Role).where(Role.name == name, Role.is_deleted == 0)
    ).scalar_one_or_none()
    if role is None:
        role = Role(name=name, description=description)
        session.add(role)
        session.flush()
    return role


def _assign_role_permissions(session, role_id: int, perm_codes: list[str]) -> None:
    """全量覆盖角色权限（先删后插）。"""
    # 删除旧关联
    session.execute(
        RolePermission.__table__.delete().where(RolePermission.role_id == role_id)
    )
    for code in perm_codes:
        perm = session.execute(
            select(Permission).where(Permission.code == code)
        ).scalar_one_or_none()
        if perm is not None:
            session.add(RolePermission(role_id=role_id, permission_id=perm.id))


def seed() -> None:
    """插入 RBAC 预置数据。"""
    session = SessionLocal()
    try:
        # 1. 创建全部权限
        perm_map: dict[str, Permission] = {}
        for code, name, module in PERMISSIONS:
            perm_map[code] = _get_or_create_permission(session, code, name, module)

        # 2. 创建角色
        admin_role = _get_or_create_role(session, "admin", ROLES["admin"])
        operator_role = _get_or_create_role(session, "operator", ROLES["operator"])

        # 3. 分配权限
        # admin：全部权限
        _assign_role_permissions(session, admin_role.id, list(perm_map.keys()))
        # operator：指定权限
        _assign_role_permissions(session, operator_role.id, OPERATOR_PERMISSIONS)

        # 4. 绑定用户角色
        # admin 用户 -> admin 角色
        admin_user = session.execute(
            select(User).where(User.username == "admin", User.is_deleted == 0)
        ).scalar_one_or_none()
        if admin_user is not None:
            admin_user.role_id = admin_role.id

        # frontend_test 用户 -> operator 角色
        ft_user = session.execute(
            select(User).where(User.username == "frontend_test", User.is_deleted == 0)
        ).scalar_one_or_none()
        if ft_user is not None:
            ft_user.role_id = operator_role.id

        session.commit()
        print("RBAC 预置数据插入成功：")
        print(f"  - 权限 {len(PERMISSIONS)} 个")
        print(f"  - 角色 {len(ROLES)} 个（admin / operator）")
        if admin_user:
            print(f"  - 用户 admin -> admin 角色")
        if ft_user:
            print(f"  - 用户 frontend_test -> operator 角色")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
