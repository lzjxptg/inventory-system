"""用户 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
创建用户时对密码进行 bcrypt 哈希，查询时默认过滤 is_deleted=0。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.security import get_password_hash
from models.user import User
from schemas.user import UserCreate


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

