"""Alembic 环境配置。

从 ``core.config.settings`` 读取数据库连接（支持 .env），
导入 ``models`` 包注册全部 ORM 模型到 ``Base.metadata``，
供 ``autogenerate`` 生成迁移脚本。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 导入项目配置与 ORM 基类
from core.config import settings
from core.database import Base

# 导入全部模型，确保表注册到 Base.metadata
import models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 用 settings.database_url 覆盖 alembic.ini 中的占位符，避免明文密码写入 ini
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标 metadata：所有模型的表结构
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
