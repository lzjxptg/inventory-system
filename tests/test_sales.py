"""销售模块单元测试。

覆盖销售订单 CRUD、状态流转、销售出库单创建/确认、超发拦截、超卖拦截、
事务一致性、库存联动、鉴权等场景。
所有测试在独立事务中运行，结束后自动回滚。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.customer import Customer
from models.inventory import InventoryBalance, StockMovement
from models.sales import (
    SalesOrder,
    SalesOrderItem,
    SalesOut,
)

ORDERS_PREFIX = "/api/v1/sales/orders"
OUTS_PREFIX = "/api/v1/sales/outs"


# ---------------------------------------------------------------------------
# 基础数据 fixture：在 setup_basic_data 基础上增加客户
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_sales_data(db_session: Session, setup_basic_data: dict) -> dict:
    """创建测试用客户，返回包含 customer_id 的完整数据字典。"""
    customer = Customer(code="CUS-TEST", name="测试客户")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    data = dict(setup_basic_data)
    data["customer_id"] = customer.id
    return data


def _seed_stock(db_session: Session, product_id: int, warehouse_id: int, quantity: str) -> None:
    """直接写入一条库存余额，供出库测试使用。"""
    balance = InventoryBalance(
        product_id=product_id,
        warehouse_id=warehouse_id,
        current_quantity=Decimal(quantity),
    )
    db_session.add(balance)
    db_session.commit()


def _create_order_payload(data: dict, quantity: str = "100", unit_price: str = "10.00") -> dict:
    """构造创建销售订单的请求体。"""
    return {
        "customer_id": data["customer_id"],
        "warehouse_id": data["warehouse_id"],
        "items": [
            {
                "product_id": data["product_id"],
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
    }


async def _approve_order(client: AsyncClient, order_id: int) -> None:
    """提交并审核订单到 approved 状态。"""
    await client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await client.post(f"{ORDERS_PREFIX}/{order_id}/approve")


# ===========================================================================
# 一、销售订单（15 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_create_order_success(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """创建订单正常：status=draft，明细 shipped_quantity=0，金额计算正确。"""
    resp = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100", "10.00"))
    assert resp.status_code == 200, f"创建订单接口返回异常: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"业务码应为0: {body}"

    order_resp = body["data"]
    assert order_resp["status"] == "draft", "新建订单状态应为 draft"
    assert order_resp["total_quantity"] == 100.0
    assert order_resp["total_amount"] == 1000.0

    order = db_session.execute(
        select(SalesOrder).where(SalesOrder.id == order_resp["id"])
    ).scalar_one()
    assert order.status == "draft"
    assert order.total_quantity == Decimal("100.00")
    assert order.total_amount == Decimal("1000.00")

    item = db_session.execute(
        select(SalesOrderItem).where(SalesOrderItem.sales_order_id == order.id)
    ).scalar_one()
    assert item.quantity == Decimal("100.00")
    assert item.unit_price == Decimal("10.00")
    assert item.amount == Decimal("1000.00")
    assert item.shipped_quantity == Decimal("0.00"), "新建明细已出库数量应为0"


@pytest.mark.asyncio
async def test_create_order_missing_required(auth_client: AsyncClient, setup_sales_data: dict):
    """缺 customer_id 或 items，预期 422。"""
    resp = await auth_client.post(ORDERS_PREFIX, json={
        "warehouse_id": setup_sales_data["warehouse_id"],
        "items": [{"product_id": setup_sales_data["product_id"], "quantity": 10, "unit_price": 5}],
    })
    assert resp.status_code == 422, f"缺 customer_id 应返回422，实际: {resp.status_code}"


@pytest.mark.asyncio
async def test_create_order_customer_not_found(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """customer_id 不存在，预期 40001。"""
    payload = _create_order_payload(setup_sales_data)
    payload["customer_id"] = 999999
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"不存在客户应返回40001: {resp.text}"

    cnt = db_session.execute(select(func.count(SalesOrder.id))).scalar()
    assert cnt == 0, "客户不存在时不应创建订单"


@pytest.mark.asyncio
async def test_create_order_product_not_found(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """product_id 不存在，预期 40001。"""
    payload = _create_order_payload(setup_sales_data)
    payload["items"][0]["product_id"] = 999999
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"不存在商品应返回40001: {resp.text}"

    cnt = db_session.execute(select(func.count(SalesOrder.id))).scalar()
    assert cnt == 0


@pytest.mark.asyncio
async def test_create_order_empty_items(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """明细为空数组，预期 422（min_length=1）。"""
    payload = _create_order_payload(setup_sales_data)
    payload["items"] = []
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 422, f"空明细应返回422，实际: {resp.status_code}"

    cnt = db_session.execute(select(func.count(SalesOrder.id))).scalar()
    assert cnt == 0


@pytest.mark.asyncio
async def test_create_order_duplicate_product(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """同一商品出现两次，预期 40001。"""
    payload = _create_order_payload(setup_sales_data)
    payload["items"].append({
        "product_id": setup_sales_data["product_id"],
        "quantity": "10",
        "unit_price": "5.00",
    })
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"重复商品应返回40001: {resp.text}"

    cnt = db_session.execute(select(func.count(SalesOrder.id))).scalar()
    assert cnt == 0


@pytest.mark.asyncio
async def test_list_orders(auth_client: AsyncClient, setup_sales_data: dict):
    """列表返回 200，含分页。"""
    await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    resp = await auth_client.get(ORDERS_PREFIX)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1


@pytest.mark.asyncio
async def test_list_orders_filter_by_status(auth_client: AsyncClient, setup_sales_data: dict):
    """按 status 筛选。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]
    await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await auth_client.get(f"{ORDERS_PREFIX}?status=submitted")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(o["status"] == "submitted" for o in data)
    assert any(o["id"] == order_id for o in data)


@pytest.mark.asyncio
async def test_list_orders_filter_by_customer(auth_client: AsyncClient, setup_sales_data: dict):
    """按 customer_id 筛选。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]

    resp = await auth_client.get(f"{ORDERS_PREFIX}?customer_id={setup_sales_data['customer_id']}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(o["customer_id"] == setup_sales_data["customer_id"] for o in data)
    assert any(o["id"] == order_id for o in data)


@pytest.mark.asyncio
async def test_get_order_detail(auth_client: AsyncClient, setup_sales_data: dict):
    """详情含 items 且字段完整。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]

    resp = await auth_client.get(f"{ORDERS_PREFIX}/{order_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["id"] == order_id
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == setup_sales_data["product_id"]
    assert data["items"][0]["shipped_quantity"] == 0.0


@pytest.mark.asyncio
async def test_update_order_in_draft(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """draft 状态可改。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100", "10.00"))
    order_id = r.json()["data"]["id"]

    update_payload = _create_order_payload(setup_sales_data, "50", "20.00")
    resp = await auth_client.put(f"{ORDERS_PREFIX}/{order_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.total_quantity == Decimal("50.00")
    assert order.total_amount == Decimal("1000.00")


@pytest.mark.asyncio
async def test_update_order_not_in_draft(auth_client: AsyncClient, setup_sales_data: dict):
    """submitted 状态改单，断言 40901。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]
    await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await auth_client.put(f"{ORDERS_PREFIX}/{order_id}", json=_create_order_payload(setup_sales_data))
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非草稿改单应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_delete_order_in_draft(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """draft 可删，is_deleted=1。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]

    resp = await auth_client.delete(f"{ORDERS_PREFIX}/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.is_deleted == 1, "逻辑删除后 is_deleted 应为 1"


@pytest.mark.asyncio
async def test_delete_order_not_in_draft(auth_client: AsyncClient, setup_sales_data: dict):
    """submitted 不可删，断言 40901。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]
    await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await auth_client.delete(f"{ORDERS_PREFIX}/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非草稿删单应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_order_no_format(auth_client: AsyncClient, setup_sales_data: dict):
    """订单号符合 SO-YYYYMMDD-序号 格式。"""
    import re
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_no = r.json()["data"]["order_no"]
    assert re.match(r"^SO-\d{8}-\d{4}$", order_no), f"订单号格式不符: {order_no}"


# ===========================================================================
# 二、状态流转（7 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_submit_order(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """draft→submitted。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]

    resp = await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.status == "submitted"


@pytest.mark.asyncio
async def test_submit_order_not_in_draft(admin_client: AsyncClient, setup_sales_data: dict):
    """非 draft 提交，断言 40901。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]
    await _approve_order(admin_client, order_id)

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非草稿提交应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_approve_order(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """submitted→approved，approved_by 有值。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.status == "approved"
    assert order.approved_by is not None


@pytest.mark.asyncio
async def test_approve_order_not_in_submitted(admin_client: AsyncClient, setup_sales_data: dict):
    """非 submitted 审核，断言 40901。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"draft 直接审核应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_approve_twice(admin_client: AsyncClient, setup_sales_data: dict):
    """重复审核，断言 40901。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]
    await _approve_order(admin_client, order_id)

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"重复审核应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_cancel_order_in_draft(auth_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """draft 可取消。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    order_id = r.json()["data"]["id"]

    resp = await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_order_completed(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """completed 不可取消，断言 40901。"""
    # 建单、审核、入库补足库存、创建并确认全额出库单 → completed
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "100"}]
    })
    out_id = out_resp.json()["data"]["id"]
    await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"completed 订单不可取消: {resp.text}"


# ===========================================================================
# 三、销售出库单（11 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_create_out_from_approved_order(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """基于 approved 订单创建入库单，落库且 status=draft。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "draft"

    out = db_session.execute(
        select(SalesOut).where(SalesOut.id == body["data"]["id"])
    ).scalar_one()
    assert out.status == "draft"
    assert out.sales_order_id == order_id


@pytest.mark.asyncio
async def test_create_out_from_draft_order(auth_client: AsyncClient, setup_sales_data: dict):
    """基于 draft 订单创建，断言 40901。"""
    r = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]

    resp = await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"draft 订单不可创建出库单: {resp.text}"


@pytest.mark.asyncio
async def test_list_outs(admin_client: AsyncClient, setup_sales_data: dict):
    """列表返回 200。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })

    resp = await admin_client.get(OUTS_PREFIX)
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert isinstance(resp.json()["data"], list)


@pytest.mark.asyncio
async def test_get_out_detail(admin_client: AsyncClient, setup_sales_data: dict):
    """详情含 items。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out_id = out_resp.json()["data"]["id"]

    resp = await admin_client.get(f"{OUTS_PREFIX}/{out_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["quantity"] == 50.0


@pytest.mark.asyncio
async def test_confirm_out_success(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """确认出库，status=confirmed，confirmed_by 有值。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out_id = out_resp.json()["data"]["id"]

    resp = await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    out = db_session.execute(select(SalesOut).where(SalesOut.id == out_id)).scalar_one()
    assert out.status == "confirmed"
    assert out.confirmed_by is not None
    assert out.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_out_over_ship(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """超发（shipped_qty + 本次 > 订购数），断言 40001，数据不变。

    通过两张出库单（60 + 50），先确认 60，再确认 50 时 60+50=110 > 100 触发超发。
    """
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "200")

    # 两张出库单：60 + 50，合计 110 > 100；create 阶段 remaining 仍为 100，均通过
    out1 = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "60"}]
    })
    out1_id = out1.json()["data"]["id"]
    out2 = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out2_id = out2.json()["data"]["id"]

    # 先确认 60，成功
    await admin_client.post(f"{OUTS_PREFIX}/{out1_id}/confirm")

    # 确认 50 时超发，预期 40001
    resp = await admin_client.post(f"{OUTS_PREFIX}/{out2_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"超发应返回40001: {resp.text}"

    # shipped_quantity 仍为 60（只有第一张出库成功）
    item = db_session.execute(
        select(SalesOrderItem).where(SalesOrderItem.id == order_item_id)
    ).scalar_one()
    assert item.shipped_quantity == Decimal("60.00"), "超发时 shipped_quantity 不应增加"

    out2_db = db_session.execute(select(SalesOut).where(SalesOut.id == out2_id)).scalar_one()
    assert out2_db.status == "draft", "超发时出库单不应被确认"


@pytest.mark.asyncio
async def test_confirm_out_insufficient_stock(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """库存不足（不入库直接出库），断言 40001，数据不变。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    # 不 seed 库存，余额为 0 / 不存在

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out_id = out_resp.json()["data"]["id"]

    resp = await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"库存不足应返回40001: {resp.text}"

    # shipped_quantity 不变
    item = db_session.execute(
        select(SalesOrderItem).where(SalesOrderItem.id == order_item_id)
    ).scalar_one()
    assert item.shipped_quantity == Decimal("0.00"), "库存不足时 shipped_quantity 不应变化"

    # 无库存余额产生
    balance_cnt = db_session.execute(select(func.count(InventoryBalance.id))).scalar()
    assert balance_cnt == 0, "库存不足时不应产生库存余额"

    # 无流水
    movement_cnt = db_session.execute(
        select(func.count(StockMovement.id)).where(StockMovement.reference_type == "SALE")
    ).scalar()
    assert movement_cnt == 0, "库存不足时不应写入流水"


@pytest.mark.asyncio
async def test_confirm_out_twice(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """重复确认，断言 40901。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out_id = out_resp.json()["data"]["id"]
    await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")

    resp = await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"重复确认应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_confirm_out_not_in_draft(admin_client: AsyncClient, setup_sales_data: dict):
    """非 draft 确认，断言 40901。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out_id = out_resp.json()["data"]["id"]
    await admin_client.post(f"{OUTS_PREFIX}/{out_id}/cancel")

    resp = await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"cancelled 状态不可确认: {resp.text}"


@pytest.mark.asyncio
async def test_partial_out_twice(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """两次分批出库，合计=订购数，订单 status=completed。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    # 第一次 60
    out1 = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "60"}]
    })
    await admin_client.post(f"{OUTS_PREFIX}/{out1.json()['data']['id']}/confirm")

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.status == "partial_out", "部分出库后状态应为 partial_out"

    # 第二次 40
    out2 = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "40"}]
    })
    await admin_client.post(f"{OUTS_PREFIX}/{out2.json()['data']['id']}/confirm")

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.status == "completed", "全部出库后状态应为 completed"

    item = db_session.execute(select(SalesOrderItem).where(SalesOrderItem.id == order_item_id)).scalar_one()
    assert item.shipped_quantity == Decimal("100.00"), "已出库数量应等于订购数"


@pytest.mark.asyncio
async def test_cancel_out_in_draft(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """draft 可取消。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out_id = out_resp.json()["data"]["id"]

    resp = await admin_client.post(f"{OUTS_PREFIX}/{out_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    out = db_session.execute(select(SalesOut).where(SalesOut.id == out_id)).scalar_one()
    assert out.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_out_confirmed(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """confirmed 不可取消，断言 40901。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "50"}]
    })
    out_id = out_resp.json()["data"]["id"]
    await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")

    resp = await admin_client.post(f"{OUTS_PREFIX}/{out_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"confirmed 出库单不可取消: {resp.text}"


# ===========================================================================
# 四、库存联动与事务（6 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_confirm_out_updates_shipped_quantity(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """shipped_quantity 累加正确。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "40"}]
    })
    await admin_client.post(f"{OUTS_PREFIX}/{out_resp.json()['data']['id']}/confirm")

    item = db_session.execute(select(SalesOrderItem).where(SalesOrderItem.id == order_item_id)).scalar_one()
    assert item.shipped_quantity == Decimal("40.00")


@pytest.mark.asyncio
async def test_confirm_out_updates_order_status_partial(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """未发齐→partial_out。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "30"}]
    })
    await admin_client.post(f"{OUTS_PREFIX}/{out_resp.json()['data']['id']}/confirm")

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.status == "partial_out"


@pytest.mark.asyncio
async def test_confirm_out_updates_order_status_completed(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """发齐→completed。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "100"}]
    })
    await admin_client.post(f"{OUTS_PREFIX}/{out_resp.json()['data']['id']}/confirm")

    order = db_session.execute(select(SalesOrder).where(SalesOrder.id == order_id)).scalar_one()
    assert order.status == "completed"


@pytest.mark.asyncio
async def test_confirm_out_decreases_inventory_balance(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """inventory_balances.current_quantity 减少量=出库量。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "40"}]
    })
    await admin_client.post(f"{OUTS_PREFIX}/{out_resp.json()['data']['id']}/confirm")

    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == setup_sales_data["product_id"],
            InventoryBalance.warehouse_id == setup_sales_data["warehouse_id"],
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("60.00"), "出库后库存应减少 40"


@pytest.mark.asyncio
async def test_confirm_out_creates_stock_movement(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session):
    """stock_movements 存在 movement_type='OUT', reference_type='SALE', reference_id=出库单id。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "40"}]
    })
    out_id = out_resp.json()["data"]["id"]
    await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")

    movement = db_session.execute(
        select(StockMovement).where(
            StockMovement.reference_type == "SALE",
            StockMovement.reference_id == out_id,
        )
    ).scalar_one()
    assert movement.movement_type == "OUT"
    assert movement.quantity == Decimal("-40.00"), "出库流水数量应为负数"


@pytest.mark.asyncio
async def test_confirm_out_atomicity(admin_client: AsyncClient, setup_sales_data: dict, db_session: Session, monkeypatch):
    """monkeypatch db.commit 抛 RuntimeError，断言订单 shipped_quantity 不变、库存余额不变、无新流水。"""
    r = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data, "100"))
    order_id = r.json()["data"]["id"]
    order_item_id = r.json()["data"]["items"][0]["id"]
    await _approve_order(admin_client, order_id)
    _seed_stock(db_session, setup_sales_data["product_id"], setup_sales_data["warehouse_id"], "100")

    out_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/outs", json={
        "items": [{"sales_order_item_id": order_item_id, "quantity": "40"}]
    })
    out_id = out_resp.json()["data"]["id"]

    def failing_commit():
        raise RuntimeError("模拟 commit 失败")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(RuntimeError):
        await admin_client.post(f"{OUTS_PREFIX}/{out_id}/confirm")

    monkeypatch.undo()

    # 回滚后 shipped_quantity 不变
    item = db_session.execute(
        select(SalesOrderItem).where(SalesOrderItem.id == order_item_id)
    ).scalar_one()
    assert item.shipped_quantity == Decimal("0.00"), "事务失败 shipped_quantity 不应变化"

    # 库存余额不变
    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == setup_sales_data["product_id"],
            InventoryBalance.warehouse_id == setup_sales_data["warehouse_id"],
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("100.00"), "事务失败库存不应变化"

    # 无新流水
    movement_cnt = db_session.execute(
        select(func.count(StockMovement.id)).where(StockMovement.reference_type == "SALE")
    ).scalar()
    assert movement_cnt == 0, "事务失败不应写入流水"


# ===========================================================================
# 五、鉴权（2 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_create_order_without_token(client: AsyncClient, setup_sales_data: dict):
    """无 Token，断言 40101。"""
    resp = await client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    assert resp.status_code == 200
    assert resp.json()["code"] == 40101, f"无 Token 应返回40101: {resp.text}"


@pytest.mark.asyncio
async def test_create_order_with_invalid_token(client: AsyncClient, setup_sales_data: dict):
    """无效 Token，断言 40101。"""
    client.headers["Authorization"] = "Bearer invalid.token.value"
    resp = await client.post(ORDERS_PREFIX, json=_create_order_payload(setup_sales_data))
    assert resp.status_code == 200
    assert resp.json()["code"] == 40101, f"无效 Token 应返回40101: {resp.text}"
