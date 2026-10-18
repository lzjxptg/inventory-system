"""用户 CRUD（示例）。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
创建用户时对密码进行 bcrypt 哈希，查询时默认过滤 is_deleted=0。
展示 BusinessException 体系的标准用法。
"""

from sqlalchemy import select
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


def create_user(db: Session, user: UserCreate) -> User:
    """新增用户，密码自动哈希。"""
    hashed = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        hashed_password=hashed,
        is_active=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
