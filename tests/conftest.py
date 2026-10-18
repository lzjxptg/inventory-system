"""pytest 测试基础设施。

- 独立测试数据库 inventory_test（不污染开发库 inventory）。
- 每个测试函数在独立事务中运行，结束后回滚，保证用例间数据隔离。
- 使用 httpx.AsyncClient + ASGITransport 测试 FastAPI 应用。
- 提供 auth_client fixture：自动创建测试用户并登录，返回带 JWT 的异步客户端。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session, sessionmaker

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models  # noqa: E402,F401  注册全部模型到 Base.metadata
from core.config import settings  # noqa: E402
from core.database import Base, get_db  # noqa: E402
from core.security import get_password_hash  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402

# 让 pytest-asyncio 自动将 async def test_* 视为协程测试
pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    """配置 pytest-asyncio 为 auto 模式。"""
    config.option.asyncio_mode = "auto"


# ---------------------------------------------------------------------------
# 测试数据库引擎
# ---------------------------------------------------------------------------

def _build_test_engine():
    """创建测试数据库（inventory_test）并返回引擎。"""
    db_url = make_url(settings.database_url)
    test_db_name = f"{db_url.database}_test"

    # 连接到 MySQL server（不指定 database），创建测试库
    server_url = db_url.set(database=None)
    server_engine = create_engine(server_url, pool_pre_ping=True)
    with server_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{test_db_name}`"))
    server_engine.dispose()

    # 指向测试库的引擎
    test_url = db_url.set(database=test_db_name)
    return create_engine(test_url, pool_pre_ping=True)


test_engine = _build_test_engine()
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def _setup_test_schema():
    """会话级：创建全部表（测试结束不删表，下次复用）。"""
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    # 会话结束后保留表结构，便于排查；如需清空可打开下一行
    # Base.metadata.drop_all(test_engine)


# ---------------------------------------------------------------------------
# 事务隔离的测试 Session
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """每个测试独占一个事务，结束后整体回滚。

    使用 join_transaction_mode="create_savepoint"，让 crud 层的 db.commit()
    只释放 savepoint 而不提交外层事务，从而保证测试数据可被回滚。
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    # 覆盖 get_db 依赖，使路由层使用该测试 session
    app.dependency_overrides[get_db] = lambda: session

    yield session

    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# 异步测试客户端
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """不带鉴权的异步测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_client(client: AsyncClient, db_session: Session):
    """带 JWT Token 的异步测试客户端。

    在测试库中创建一个测试用户，通过登录接口换取 Token，
    并将 Authorization: Bearer <token> 写入请求头。
    """
    username = "testuser"
    password = "testpass123"

    # 直接在测试 session 中创建用户
    user = User(
        username=username,
        hashed_password=get_password_hash(password),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # 调用登录接口获取 Token
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    token = resp.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    yield client


# ---------------------------------------------------------------------------
# 业务基础数据（仓库/单位/分类/商品）fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_basic_data(db_session: Session):
    """创建测试用的仓库、单位、分类、商品，返回各实体 id。"""
    from models.category import Category
    from models.product import Product
    from models.unit import Unit
    from models.warehouse import Warehouse

    warehouse = Warehouse(code="WH-TEST", name="测试仓库")
    unit = Unit(name="个")
    category = Category(name="测试分类")
    db_session.add_all([warehouse, unit, category])
    db_session.commit()
    db_session.refresh(warehouse)
    db_session.refresh(unit)
    db_session.refresh(category)

    product = Product(
        sku="SKU-TEST-001",
        name="测试商品",
        category_id=category.id,
        unit_id=unit.id,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    return {
        "warehouse_id": warehouse.id,
        "unit_id": unit.id,
        "category_id": category.id,
        "product_id": product.id,
    }
