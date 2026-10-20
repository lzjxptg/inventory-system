#!/bin/sh
set -e

echo "[entrypoint] 等待数据库就绪..."
python -c "
import time
from sqlalchemy import create_engine, text
from core.config import settings
for i in range(30):
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('[entrypoint] 数据库已就绪')
        break
    except Exception as e:
        print(f'[entrypoint] 等待数据库... ({i+1}/30) {e}')
        time.sleep(2)
else:
    print('[entrypoint] 数据库连接超时，启动失败')
    exit(1)
"

echo "[entrypoint] 执行数据库迁移 (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] 初始化角色与权限 (seed_roles.py)..."
python scripts/seed_roles.py

echo "[entrypoint] 启动应用..."
exec uvicorn main:app --host 0.0.0.0 --port 8002
