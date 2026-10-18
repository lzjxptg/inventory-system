"""初始化数据库：根据 models 创建所有表。

适用于开发环境快速建表；生产环境请使用 Alembic 迁移：
    alembic upgrade head
"""

import models  # noqa: F401  注册全部模型到 Base.metadata
from core.database import Base, engine


def init_db() -> None:
    """创建所有表（已存在的表不会被重建）。"""
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成")


if __name__ == "__main__":
    init_db()
