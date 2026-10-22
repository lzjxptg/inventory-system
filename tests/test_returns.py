"""采购退货与销售退货模块测试。

覆盖：
- 采购退货：创建、列表、提交、审核通过（验证库存增加+IN流水）、删除草稿、超量退货拦截
- 销售退货：创建、审核通过（验证库存增加+IN流水）
所有测试在独立事务中运行，结束后自动回滚。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import get_password_hash
from models.inventory import InventoryBalance, StockMovement
from models.product import Product
from models.role import Permission, Role, RolePermission
from models.supplier import Supplier
from models.customer import Customer
from models.user import User

PURCHASE_RETURN_PREFIX = "/api/v1/purchase-returns"
SALES_RETURN_PREFIX = "/api/v1/sales-returns"
PURCHASE_ORDERS_PREFIX = "/api/v1/purchases/orders"
PURCHASE_INS_PREFIX = "/api/v1/purchases/ins"
SALES_ORDERS_PREFIX = "/api/v1/sales/orders"
SALES_OUTS_PREFIX = "/api/v1/sales/outs"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_client(client: AsyncClient, db_session: Session):
    """带 admin 角色且拥有退货相关权限的测试客户端。"""
    role = Role(name="admin", description="管理员")
    db_session.add(role)
    db_session.flush()

    perms = [
        Permission(code="purchase_return:view", name="查看采购退货", module="purchase_return"),
        Permission(code="purchase_return:create", name="创建采购退货", module="purchase_return"),
        Permission(code="purchase_return:approve", name="审核采购退货", module="purchase_return"),
        Permission(code="sales_return:view", name="查看销售退货", module="sales_return"),
        Permission(code="sales_return:create", name="创建销售退货", module="sales_return"),
        Permission(code="sales_return:approve", name="审核销售退货", module="sales_return"),
    ]
    db_session.add_all(perms)
    db_session.flush()
    for p in perms:
        db_session.add(RolePermission(role_id=role.id, permission_id=p.id))

    user = User(
        username="admintest",
        hashed_password=get_password_hash("adminpass123"),
        is_active=True,
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "admintest", "password": "adminpass123"},
    )
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


@pytest.fixture
def setup_return_data(db_session: Session, setup_basic_data: dict) -> dict:
    """创建供应商和客户，返回完整数据字典。"""
    supplier = Supplier(code="SUP-RET", name="退货测试供应商")
    customer = Customer(code="CUS-RET", name="退货测试客户")
    db_session.add_all([supplier, customer])
    db_session.commit()
    db_session.refresh(supplier)
    db_session.refresh(customer)

    data = dict(setup_basic_data)
    data["supplier_id"] = supplier.id
    data["customer_id"] = customer.id
    return data


def _balance(db: Session, product_id: int, warehouse_id: int) -> Decimal:
    b = db.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == product_id,
            InventoryBalance.warehouse_id == warehouse_id,
            InventoryBalance.is_deleted == 0,
        )
    ).scalar_one_or_none()
    return b.current_quantity if b is not None else Decimal("0")


# ===========================================================================
# 采购退货
# ===========================================================================


@pytest.mark.asyncio
async def test_purchase_return_create_and_approve_increases_stock(
    admin_client: AsyncClient, setup_return_data: dict, db_session: Session
):
    """采购退货审核通过后，库存余额增加，写入 IN 流水。"""
    d = setup_return_data
    pid = d["product_id"]
    wid = d["warehouse_id"]

    # 1. 创建采购订单
    r = await admin_client.post(PURCHASE_ORDERS_PREFIX, json={
        "supplier_id": d["supplier_id"],
        "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": 100, "unit_price": 10}],
    })
    order_id = r.json()["data"]["id"]

    # 2. 审核订单
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/approve")

    # 3. 创建并确认入库（received_quantity = 100）
    r = await admin_client.get(f"{PURCHASE_ORDERS_PREFIX}/{order_id}")
    order_item_id = r.json()["data"]["items"][0]["id"]
    r = await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": 100}],
    })
    in_id = r.json()["data"]["id"]
    await admin_client.post(f"{PURCHASE_INS_PREFIX}/{in_id}/confirm")

    # 当前库存应为 100
    assert _balance(db_session, pid, wid) == Decimal("100.00")

    # 4. 创建采购退货单（退 30）
    r = await admin_client.post(PURCHASE_RETURN_PREFIX, json={
        "purchase_order_id": order_id,
        "reason": "质量问题",
        "items": [{"product_id": pid, "quantity": 30, "unit_price": 10}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    ret_id = body["data"]["id"]
    assert body["data"]["status"] == "draft"
    assert body["data"]["total_quantity"] == 30.0
    assert body["data"]["total_amount"] == 300.0

    # 5. 提交 + 审核通过
    await admin_client.post(f"{PURCHASE_RETURN_PREFIX}/{ret_id}/submit")
    r = await admin_client.post(f"{PURCHASE_RETURN_PREFIX}/{ret_id}/approve")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "approved"

    # 6. 库存应增加到 130（退回仓库）
    db_session.expire_all()
    assert _balance(db_session, pid, wid) == Decimal("130.00")

    # 7. 存在 PURCHASE_RETURN 的 IN 流水
    mv = db_session.execute(
        select(StockMovement).where(
            StockMovement.reference_type == "PURCHASE_RETURN",
            StockMovement.reference_id == ret_id,
        )
    ).scalar_one()
    assert mv.movement_type == "IN"
    assert mv.quantity == Decimal("30.00")


@pytest.mark.asyncio
async def test_purchase_return_quantity_exceeds_received(
    admin_client: AsyncClient, setup_return_data: dict, db_session: Session
):
    """退货数量超过已入库数量应返回 40001。"""
    d = setup_return_data
    pid, wid = d["product_id"], d["warehouse_id"]

    r = await admin_client.post(PURCHASE_ORDERS_PREFIX, json={
        "supplier_id": d["supplier_id"],
        "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": 100, "unit_price": 10}],
    })
    order_id = r.json()["data"]["id"]
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/approve")

    # 未入库，received_quantity=0，退货 10 应失败
    r = await admin_client.post(PURCHASE_RETURN_PREFIX, json={
        "purchase_order_id": order_id,
        "items": [{"product_id": pid, "quantity": 10, "unit_price": 10}],
    })
    assert r.status_code == 200
    assert r.json()["code"] == 40001


@pytest.mark.asyncio
async def test_purchase_return_delete_draft_only(
    admin_client: AsyncClient, setup_return_data: dict, db_session: Session
):
    """仅草稿可删除；已提交的退货单删除应返回冲突。"""
    d = setup_return_data
    pid, wid = d["product_id"], d["warehouse_id"]

    r = await admin_client.post(PURCHASE_ORDERS_PREFIX, json={
        "supplier_id": d["supplier_id"],
        "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": 100, "unit_price": 10}],
    })
    order_id = r.json()["data"]["id"]
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/approve")
    r = await admin_client.get(f"{PURCHASE_ORDERS_PREFIX}/{order_id}")
    order_item_id = r.json()["data"]["items"][0]["id"]
    r = await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": 100}],
    })
    in_id = r.json()["data"]["id"]
    await admin_client.post(f"{PURCHASE_INS_PREFIX}/{in_id}/confirm")

    r = await admin_client.post(PURCHASE_RETURN_PREFIX, json={
        "purchase_order_id": order_id,
        "items": [{"product_id": pid, "quantity": 10, "unit_price": 10}],
    })
    ret_id = r.json()["data"]["id"]

    # 提交后删除应失败
    await admin_client.post(f"{PURCHASE_RETURN_PREFIX}/{ret_id}/submit")
    r = await admin_client.delete(f"{PURCHASE_RETURN_PREFIX}/{ret_id}")
    assert r.json()["code"] != 0


@pytest.mark.asyncio
async def test_purchase_return_list(
    admin_client: AsyncClient, setup_return_data: dict
):
    """列表接口正常返回。"""
    r = await admin_client.get(PURCHASE_RETURN_PREFIX)
    assert r.status_code == 200
    assert r.json()["code"] == 0
    assert isinstance(r.json()["data"], list)


# ===========================================================================
# 销售退货
# ===========================================================================


@pytest.mark.asyncio
async def test_sales_return_approve_increases_stock(
    admin_client: AsyncClient, setup_return_data: dict, db_session: Session
):
    """销售退货审核通过后，库存余额增加，写入 IN 流水。"""
    d = setup_return_data
    pid, wid = d["product_id"], d["warehouse_id"]

    # 1. 先入库 100（通过采购入库）
    r = await admin_client.post(PURCHASE_ORDERS_PREFIX, json={
        "supplier_id": d["supplier_id"],
        "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": 100, "unit_price": 10}],
    })
    porder_id = r.json()["data"]["id"]
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{porder_id}/submit")
    await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{porder_id}/approve")
    r = await admin_client.get(f"{PURCHASE_ORDERS_PREFIX}/{porder_id}")
    pitem_id = r.json()["data"]["items"][0]["id"]
    r = await admin_client.post(f"{PURCHASE_ORDERS_PREFIX}/{porder_id}/ins", json={
        "items": [{"purchase_order_item_id": pitem_id, "quantity": 100}],
    })
    await admin_client.post(f"{PURCHASE_INS_PREFIX}/{r.json()['data']['id']}/confirm")
    assert _balance(db_session, pid, wid) == Decimal("100.00")

    # 2. 创建销售订单并审核
    r = await admin_client.post(SALES_ORDERS_PREFIX, json={
        "customer_id": d["customer_id"],
        "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": 50, "unit_price": 15}],
    })
    sorder_id = r.json()["data"]["id"]
    await admin_client.post(f"{SALES_ORDERS_PREFIX}/{sorder_id}/submit")
    await admin_client.post(f"{SALES_ORDERS_PREFIX}/{sorder_id}/approve")

    # 3. 确认出库（shipped_quantity = 50），库存 = 100 - 50 = 50
    r = await admin_client.get(f"{SALES_ORDERS_PREFIX}/{sorder_id}")
    sitem_id = r.json()["data"]["items"][0]["id"]
    r = await admin_client.post(f"{SALES_ORDERS_PREFIX}/{sorder_id}/outs", json={
        "items": [{"sales_order_item_id": sitem_id, "quantity": 50}],
    })
    out_id = r.json()["data"]["id"]
    await admin_client.post(f"{SALES_OUTS_PREFIX}/{out_id}/confirm")
    db_session.expire_all()
    assert _balance(db_session, pid, wid) == Decimal("50.00")

    # 4. 创建销售退货单（退 30，IN 入库）
    r = await admin_client.post(SALES_RETURN_PREFIX, json={
        "sales_order_id": sorder_id,
        "reason": "客户退货",
        "items": [{"product_id": pid, "quantity": 30, "unit_price": 15}],
    })
    assert r.json()["code"] == 0
    ret_id = r.json()["data"]["id"]

    # 5. 提交 + 审核通过
    await admin_client.post(f"{SALES_RETURN_PREFIX}/{ret_id}/submit")
    r = await admin_client.post(f"{SALES_RETURN_PREFIX}/{ret_id}/approve")
    assert r.json()["data"]["status"] == "approved"

    # 6. 库存应增加到 80（50 + 30）
    db_session.expire_all()
    assert _balance(db_session, pid, wid) == Decimal("80.00")

    # 7. 存在 SALES_RETURN 的 IN 流水
    mv = db_session.execute(
        select(StockMovement).where(
            StockMovement.reference_type == "SALES_RETURN",
            StockMovement.reference_id == ret_id,
        )
    ).scalar_one()
    assert mv.movement_type == "IN"
    assert mv.quantity == Decimal("30.00")
