"""角色与权限 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
角色/权限/关联均采用逻辑删除（is_deleted=0 过滤）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.role import Permission, Role, RolePermission
from schemas.role import RoleCreate, RoleUpdate


def get_role(db: Session, role_id: int) -> Role | None:
    """根据 ID 查询单个未删除角色。"""
    stmt = select(Role).where(Role.id == role_id, Role.is_deleted == 0)
    return db.execute(stmt).scalar_one_or_none()


def get_role_by_name(db: Session, name: str) -> Role | None:
    """根据角色编码查询未删除角色。"""
    stmt = select(Role).where(Role.name == name, Role.is_deleted == 0)
    return db.execute(stmt).scalar_one_or_none()


def list_roles(db: Session, skip: int = 0, limit: int = 100) -> list[Role]:
    """分页查询未删除角色列表。"""
    stmt = (
        select(Role)
        .where(Role.is_deleted == 0)
        .order_by(Role.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_role(db: Session, role_in: RoleCreate) -> Role:
    """新建角色。角色编码唯一，重复抛出 400。"""
    if get_role_by_name(db, role_in.name) is not None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"角色编码 {role_in.name} 已存在",
        )
    db_role = Role(**role_in.model_dump())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role


def update_role(db: Session, role_id: int, role_in: RoleUpdate) -> Role | None:
    """更新角色。若修改 name，校验唯一。"""
    db_role = get_role(db, role_id)
    if db_role is None:
        return None
    update_data = role_in.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != db_role.name:
        if get_role_by_name(db, update_data["name"]) is not None:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"角色编码 {update_data['name']} 已存在",
            )
    for field, value in update_data.items():
        setattr(db_role, field, value)
    db.commit()
    db.refresh(db_role)
    return db_role


def delete_role(db: Session, role_id: int) -> bool:
    """逻辑删除角色。"""
    db_role = get_role(db, role_id)
    if db_role is None:
        return False
    db_role.is_deleted = 1
    db.commit()
    return True


# ---------------- 权限 ----------------

def list_permissions(db: Session) -> list[Permission]:
    """查询全部未删除权限，按 module、id 排序。"""
    stmt = (
        select(Permission)
        .where(Permission.is_deleted == 0)
        .order_by(Permission.module.asc(), Permission.id.asc())
    )
    return db.execute(stmt).scalars().all()


def get_permissions_by_ids(db: Session, ids: list[int]) -> list[Permission]:
    """根据 ID 列表查询未删除权限。"""
    if not ids:
        return []
    stmt = select(Permission).where(
        Permission.id.in_(ids), Permission.is_deleted == 0
    )
    return db.execute(stmt).scalars().all()


# ---------------- 角色-权限关联 ----------------

def get_role_permission_ids(db: Session, role_id: int) -> list[int]:
    """查询角色已分配的权限 ID 列表。"""
    stmt = select(RolePermission.permission_id).where(
        RolePermission.role_id == role_id, RolePermission.is_deleted == 0
    )
    return list(db.execute(stmt).scalars().all())


def assign_role_permissions(
    db: Session, role_id: int, permission_ids: list[int]
) -> None:
    """全量覆盖角色权限：先删除旧关联，再插入新关联。"""
    # 校验角色存在
    if get_role(db, role_id) is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="角色不存在"
        )
    # 校验权限全部存在
    valid = get_permissions_by_ids(db, permission_ids)
    if len(valid) != len(set(permission_ids)):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="存在无效的权限ID"
        )
    # 删除旧关联
    db.execute(
        RolePermission.__table__.delete().where(
            RolePermission.role_id == role_id
        )
    )
    # 插入新关联
    for pid in permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=pid))
    db.commit()


def get_permission_codes_by_role_id(db: Session, role_id: int) -> list[str]:
    """根据角色 ID 查询其拥有的权限 code 列表。"""
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(
            RolePermission.role_id == role_id,
            RolePermission.is_deleted == 0,
            Permission.is_deleted == 0,
        )
    )
    return list(db.execute(stmt).scalars().all())
