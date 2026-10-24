"""用户 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
创建用户时对密码进行 bcrypt 哈希，查询时默认过滤 is_deleted=0。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.exceptions import ConflictException, NotFoundException
from core.security import get_password_hash
from models.role import Role
from models.user import User
from schemas.user import UserCreate, UserUpdate


def get_user_by_username(db: Session, username: str) -> User | None:
    """根据用户名查询未删除用户。"""
    stmt = select(User).where(
        User.username == username,
        User.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """根据 ID 查询未删除用户。"""
    stmt = select(User).where(User.id == user_id, User.is_deleted == 0)
    return db.execute(stmt).scalar_one_or_none()


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """分页查询未删除用户列表。"""
    stmt = (
        select(User)
        .where(User.is_deleted == 0)
        .order_by(User.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_user(db: Session, user: UserCreate) -> User:
    """新增用户，密码自动哈希；role_id 为 None 时不设置（默认 operator）。"""
    hashed = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        hashed_password=hashed,
        is_active=True,
        role_id=user.role_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def assign_user_role(db: Session, user_id: int, role_id: int) -> User | None:
    """为用户分配角色。用户不存在返回 None。"""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    db_user.role_id = role_id
    db.commit()
    db.refresh(db_user)
    return db_user


def soft_delete_user(db: Session, user_id: int) -> bool:
    """逻辑删除用户（is_deleted=1）。用户不存在返回 False。"""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return False
    db_user.is_deleted = 1
    db.commit()
    return True


def update_user_password(db: Session, user_id: int, new_password: str) -> User | None:
    """更新用户密码（明文转 bcrypt 哈希）。用户不存在返回 None。"""
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None
    db_user.hashed_password = get_password_hash(new_password)
    db.commit()
    db.refresh(db_user)
    return db_user


def count_active_admins(db: Session, admin_role_id: int) -> int:
    """统计拥有指定 admin 角色的启用且未删除用户数量。"""
    stmt = select(func.count(User.id)).where(
        User.role_id == admin_role_id,
        User.is_deleted == 0,
        User.is_active.is_(True),
    )
    return int(db.execute(stmt).scalar_one() or 0)


def count_users_by_role(db: Session, role_key: str) -> int:
    """根据角色编码（name）统计启用且未删除的用户数量。

    角色不存在时返回 0。
    """
    role = db.execute(
        select(Role).where(Role.name == role_key, Role.is_deleted == 0)
    ).scalar_one_or_none()
    if role is None:
        return 0
    stmt = select(func.count(User.id)).where(
        User.role_id == role.id,
        User.is_deleted == 0,
        User.is_active.is_(True),
    )
    return int(db.execute(stmt).scalar_one() or 0)


def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User | None:
    """更新用户信息（用户名/角色/密码）。

    - 用户不存在返回 None
    - 修改用户名时校验唯一性，重复抛出 ConflictException
    - password 字段非空时才更新密码哈希
    - role_id 显式传入（含 None）时更新角色
    """
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        return None

    update_data = user_in.model_dump(exclude_unset=True)

    # 用户名唯一性校验
    if "username" in update_data and update_data["username"] != db_user.username:
        if get_user_by_username(db, update_data["username"]) is not None:
            raise ConflictException(f"用户名 {update_data['username']} 已存在")

    # 角色存在性校验
    if "role_id" in update_data and update_data["role_id"] is not None:
        from crud.role import get_role

        if get_role(db, update_data["role_id"]) is None:
            from core.exceptions import ValidationException

            raise ValidationException("指定的角色不存在")

    for field, value in update_data.items():
        if field == "password":
            if value:  # 仅在提供新密码时更新哈希
                db_user.hashed_password = get_password_hash(value)
            continue
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int, operator_id: int) -> bool:
    """逻辑删除用户，附带安全校验。

    - 用户不存在 → NotFoundException
    - 不能删除当前登录账号 → ConflictException
    - 若目标用户是 admin 且为最后一个启用的 admin → ConflictException
    """
    db_user = get_user_by_id(db, user_id)
    if db_user is None:
        raise NotFoundException("用户不存在")

    # 不能删除自己
    if user_id == operator_id:
        raise ConflictException("不能删除当前登录账号")

    # 若目标用户是 admin，检查是否为最后一个启用的 admin
    admin_role = db.execute(
        select(Role).where(Role.name == "admin", Role.is_deleted == 0)
    ).scalar_one_or_none()
    if admin_role is not None and db_user.role_id == admin_role.id:
        if count_active_admins(db, admin_role.id) <= 1:
            raise ConflictException(
                "当前为唯一管理员，无法删除。请先为其他用户分配管理员角色后再操作"
            )

    db_user.is_deleted = 1
    db.commit()
    return True

