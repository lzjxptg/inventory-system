from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# 创建数据库引擎
# pool_pre_ping=True：每次从连接池取连接前先探测，避免使用已断开的连接
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug,
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类，所有 ORM 模型继承此类。"""

    pass


def get_db() -> Generator:
    """FastAPI 依赖：获取数据库会话，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
