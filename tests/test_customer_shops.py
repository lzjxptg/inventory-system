"""客户门店模块测试。

覆盖：
- 门店创建（正常、同客户重名拦截、无效客户拦截）
- 门店列表按客户筛选
- 设默认门店（同客户其他门店取消默认）
- 门店删除
- 销售订单关联门店（创建时传 shop_id，详情返回 shop_name；
  shop_id 不属于所选客户时拦截）
所有测试在独立事务中运行，结束后自动回滚。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import get_password_hash
from models.customer import Customer
from models.customer_shop import CustomerShop
from models.role import Permission, Role, RolePermission
from models.user import User

CUSTOMER_SHOPS_PREFIX = "/api/v1/customer-shops"
SALES_ORDERS_PREFIX = "/api/v1/sales/orders"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def shop_client(client: AsyncClient, db_session: Session):
    """拥有 customer:view / customer:create 权限的测试客户端。"""
    role = Role(name="admin", description="管理员")
    db_session.add(role)
    db_session.flush()

    perms = [
        Permission(code="customer:view", name="查看客户/门店", module="customer"),
        Permission(code="customer:create", name="创建/编辑/删除客户及门店", module="customer"),
    ]
    db_session.add_all(perms)
    db_session.flush()
    for p in perms:
        db_session.add(RolePermission(role_id=role.id, permission_id=p.id))

    user = User(
        username="shoptest",
        hashed_password=get_password_hash("shoppass123"),
        is_active=True,
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "shoptest", "password": "shoppass123"},
    )
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


@pytest.fixture
def setup_customer(db_session: Session) -> int:
    """创建一个测试客户，返回客户 id。"""
    customer = Customer(code="C-SHOP", name="连锁超市")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer.id


# ---------------------------------------------------------------------------
# 门店 CRUD 测试
# ---------------------------------------------------------------------------


async def test_create_shop_success(shop_client: AsyncClient, setup_customer: int):
    """正常创建门店。"""
    cid = setup_customer
    resp = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX,
        json={"customer_id": cid, "shop_name": "朝阳店", "is_default": 1},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["shop_name"] == "朝阳店"
    assert data["customer_id"] == cid
    assert data["is_default"] == 1


async def test_create_shop_duplicate_name(shop_client: AsyncClient, setup_customer: int):
    """同客户下门店名称重复应返回 40001。"""
    cid = setup_customer
    await shop_client.post(
        CUSTOMER_SHOPS_PREFIX,
        json={"customer_id": cid, "shop_name": "海淀店"},
    )
    resp = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX,
        json={"customer_id": cid, "shop_name": "海淀店"},
    )
    assert resp.json()["code"] == 40001


async def test_create_shop_invalid_customer(shop_client: AsyncClient):
    """客户不存在时应返回 40401。"""
    resp = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX,
        json={"customer_id": 99999, "shop_name": "不存在"},
    )
    assert resp.json()["code"] == 40401


async def test_list_shops_by_customer(shop_client: AsyncClient, setup_customer: int):
    """按客户查询门店列表。"""
    cid = setup_customer
    await shop_client.post(
        CUSTOMER_SHOPS_PREFIX, json={"customer_id": cid, "shop_name": "门店A"}
    )
    await shop_client.post(
        CUSTOMER_SHOPS_PREFIX, json={"customer_id": cid, "shop_name": "门店B"}
    )
    resp = await shop_client.get(f"{CUSTOMER_SHOPS_PREFIX}?customer_id={cid}")
    data = resp.json()["data"]
    assert len(data) == 2


async def test_set_default_shop(shop_client: AsyncClient, setup_customer: int, db_session: Session):
    """设默认门店后，同客户其他门店 is_default 应为 0。"""
    cid = setup_customer
    r1 = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX, json={"customer_id": cid, "shop_name": "门店A", "is_default": 1}
    )
    r2 = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX, json={"customer_id": cid, "shop_name": "门店B"}
    )
    shop_b_id = r2.json()["data"]["id"]

    # 将门店B设为默认
    await shop_client.post(f"{CUSTOMER_SHOPS_PREFIX}/{shop_b_id}/set-default")

    shops = db_session.execute(
        select(CustomerShop).where(CustomerShop.customer_id == cid, CustomerShop.is_deleted == 0)
    ).scalars().all()
    defaults = [s for s in shops if s.is_default == 1]
    assert len(defaults) == 1
    assert defaults[0].id == shop_b_id


async def test_delete_shop(shop_client: AsyncClient, setup_customer: int):
    """删除门店后列表中不再出现。"""
    cid = setup_customer
    r = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX, json={"customer_id": cid, "shop_name": "待删除"}
    )
    shop_id = r.json()["data"]["id"]

    resp = await shop_client.delete(f"{CUSTOMER_SHOPS_PREFIX}/{shop_id}")
    assert resp.json()["code"] == 0

    lst = await shop_client.get(f"{CUSTOMER_SHOPS_PREFIX}?customer_id={cid}")
    assert all(s["id"] != shop_id for s in lst.json()["data"])


# ---------------------------------------------------------------------------
# 销售订单关联门店测试
# ---------------------------------------------------------------------------


async def test_sales_order_with_shop_id(
    shop_client: AsyncClient, setup_customer: int, setup_basic_data: dict, db_session: Session
):
    """销售订单传 shop_id 创建成功，详情返回 shop_name。"""
    cid = setup_customer
    r = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX, json={"customer_id": cid, "shop_name": "配送店"}
    )
    shop_id = r.json()["data"]["id"]

    body = {
        "customer_id": cid,
        "warehouse_id": setup_basic_data["warehouse_id"],
        "shop_id": shop_id,
        "items": [{"product_id": setup_basic_data["product_id"], "quantity": 1, "unit_price": 10}],
    }
    resp = await shop_client.post(SALES_ORDERS_PREFIX, json=body)
    assert resp.status_code == 200
    order_id = resp.json()["data"]["id"]

    detail = await shop_client.get(f"{SALES_ORDERS_PREFIX}/{order_id}")
    data = detail.json()["data"]
    assert data["shop_id"] == shop_id
    assert data["shop_name"] == "配送店"


async def test_sales_order_shop_not_belong_to_customer(
    shop_client: AsyncClient, setup_customer: int, setup_basic_data: dict, db_session: Session
):
    """shop_id 不属于所选客户时应返回 40001。"""
    cid = setup_customer
    other = Customer(code="C-OTHER", name="其他客户")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    # 在 other 客户下建门店
    r = await shop_client.post(
        CUSTOMER_SHOPS_PREFIX, json={"customer_id": other.id, "shop_name": "别家门店"}
    )
    shop_id = r.json()["data"]["id"]

    body = {
        "customer_id": cid,  # 用 cid，但门店属于 other
        "warehouse_id": setup_basic_data["warehouse_id"],
        "shop_id": shop_id,
        "items": [{"product_id": setup_basic_data["product_id"], "quantity": 1, "unit_price": 10}],
    }
    resp = await shop_client.post(SALES_ORDERS_PREFIX, json=body)
    assert resp.json()["code"] == 40001
