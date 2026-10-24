"""采购模块单元测试。

覆盖采购订单 CRUD、状态流转、采购入库单创建/确认、超收拦截、
事务一致性、库存联动、鉴权等场景。
所有测试在独立事务中运行，结束后自动回滚。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.inventory import InventoryBalance, StockMovement
from models.purchase import (
    PurchaseIn,
    PurchaseInItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from models.supplier import Supplier

ORDERS_PREFIX = "/api/v1/purchases/orders"
INS_PREFIX = "/api/v1/purchases/ins"


# ---------------------------------------------------------------------------
# 基础数据 fixture：在 setup_basic_data 基础上增加供应商
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_purchase_data(db_session: Session, setup_basic_data: dict) -> dict:
    """创建测试用供应商，返回包含 supplier_id 的完整数据字典。"""
    supplier = Supplier(code="SUP-TEST", name="测试供应商")
    db_session.add(supplier)
    db_session.commit()
    db_session.refresh(supplier)

    data = dict(setup_basic_data)
    data["supplier_id"] = supplier.id
    return data


def _create_order_payload(data: dict, quantity: str = "100", unit_price: str = "10.00") -> dict:
    """构造创建采购订单的请求体。"""
    return {
        "supplier_id": data["supplier_id"],
        "warehouse_id": data["warehouse_id"],
        "items": [
            {
                "product_id": data["product_id"],
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
    }


# ===========================================================================
# 一、采购订单（15 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_create_order_success(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """创建订单正常：status=draft，明细 received_quantity=0，金额计算正确。"""
    order_data = _create_order_payload(setup_purchase_data, quantity="100", unit_price="10.00")
    resp = await auth_client.post(ORDERS_PREFIX, json=order_data)
    assert resp.status_code == 200, f"创建订单接口返回异常: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"业务码应为0: {body}"

    order_resp = body["data"]
    assert order_resp["status"] == "draft", "新建订单状态应为 draft"
    assert order_resp["total_quantity"] == 100.0, "总数量应为100"
    assert order_resp["total_amount"] == 1000.0, "总金额应为1000"

    # 查库核对
    order = db_session.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == order_resp["id"])
    ).scalar_one()
    assert order.status == "draft"
    assert order.total_quantity == Decimal("100.00")
    assert order.total_amount == Decimal("1000.00")

    item = db_session.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == order.id)
    ).scalar_one()
    assert item.quantity == Decimal("100.00")
    assert item.unit_price == Decimal("10.00")
    assert item.amount == Decimal("1000.00")
    assert item.received_quantity == Decimal("0.00"), "新建明细已入库数量应为0"


@pytest.mark.asyncio
async def test_create_order_missing_required(auth_client: AsyncClient, setup_purchase_data: dict):
    """缺 supplier_id 或 items，预期 422。"""
    # 缺 supplier_id
    resp = await auth_client.post(ORDERS_PREFIX, json={
        "warehouse_id": setup_purchase_data["warehouse_id"],
        "items": [{"product_id": setup_purchase_data["product_id"], "quantity": 10, "unit_price": 5}],
    })
    assert resp.status_code == 422, f"缺 supplier_id 应返回422，实际: {resp.status_code}"


@pytest.mark.asyncio
async def test_create_order_supplier_not_found(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """supplier_id 不存在，预期 40001。"""
    payload = _create_order_payload(setup_purchase_data)
    payload["supplier_id"] = 999999
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"不存在供应商应返回40001: {resp.text}"

    cnt = db_session.execute(select(func.count(PurchaseOrder.id))).scalar()
    assert cnt == 0, "供应商不存在时不应创建订单"


@pytest.mark.asyncio
async def test_create_order_product_not_found(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """product_id 不存在，预期 40001。"""
    payload = _create_order_payload(setup_purchase_data)
    payload["items"][0]["product_id"] = 999999
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"不存在商品应返回40001: {resp.text}"

    cnt = db_session.execute(select(func.count(PurchaseOrder.id))).scalar()
    assert cnt == 0, "商品不存在时不应创建订单"


@pytest.mark.asyncio
async def test_create_order_empty_items(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """明细为空数组，预期 422（min_length=1）。"""
    payload = _create_order_payload(setup_purchase_data)
    payload["items"] = []
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 422, f"空明细应返回422，实际: {resp.status_code}"


@pytest.mark.asyncio
async def test_create_order_duplicate_product(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """同一商品出现两次，预期 40001。"""
    payload = _create_order_payload(setup_purchase_data)
    payload["items"].append({
        "product_id": setup_purchase_data["product_id"],
        "quantity": 20,
        "unit_price": 8,
    })
    resp = await auth_client.post(ORDERS_PREFIX, json=payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"重复商品应返回40001: {resp.text}"

    cnt = db_session.execute(select(func.count(PurchaseOrder.id))).scalar()
    assert cnt == 0, "重复商品时不应创建订单"


@pytest.mark.asyncio
async def test_list_orders(auth_client: AsyncClient, setup_purchase_data: dict):
    """列表返回 200，含数据。"""
    await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    resp = await auth_client.get(ORDERS_PREFIX)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1, f"应有1条订单，实际{len(data)}"


@pytest.mark.asyncio
async def test_list_orders_filter_by_status(auth_client: AsyncClient, setup_purchase_data: dict):
    """按 status 筛选。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    # 筛选 submitted
    resp = await auth_client.get(ORDERS_PREFIX, params={"status": "submitted"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1, f"筛选 submitted 应有1条，实际{len(data)}"
    assert data[0]["status"] == "submitted"

    # 筛选 draft 应为空
    resp2 = await auth_client.get(ORDERS_PREFIX, params={"status": "draft"})
    assert resp2.json()["data"] == [], "draft 状态应为空"


@pytest.mark.asyncio
async def test_list_orders_filter_by_supplier(auth_client: AsyncClient, setup_purchase_data: dict):
    """按 supplier_id 筛选。"""
    await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    resp = await auth_client.get(ORDERS_PREFIX, params={"supplier_id": setup_purchase_data["supplier_id"]})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    resp2 = await auth_client.get(ORDERS_PREFIX, params={"supplier_id": 999999})
    assert resp2.json()["data"] == [], "不存在的供应商应返回空"


@pytest.mark.asyncio
async def test_get_order_detail(auth_client: AsyncClient, setup_purchase_data: dict):
    """详情含 items 且字段完整。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]

    resp = await auth_client.get(f"{ORDERS_PREFIX}/{order_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == order_id
    assert len(data["items"]) == 1, "详情应包含1条明细"
    assert data["items"][0]["product_id"] == setup_purchase_data["product_id"]
    assert "product_name" in data["items"][0]
    assert "supplier_name" in data
    assert "warehouse_name" in data


@pytest.mark.asyncio
async def test_update_order_in_draft(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """draft 状态可改。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]

    update_payload = _create_order_payload(setup_purchase_data, quantity="200", unit_price="20.00")
    resp = await auth_client.put(f"{ORDERS_PREFIX}/{order_id}", json=update_payload)
    assert resp.status_code == 200, f"修改订单失败: {resp.text}"
    assert resp.json()["code"] == 0

    # 查库核对
    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.total_quantity == Decimal("200.00")
    assert order.total_amount == Decimal("4000.00")
    item = db_session.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == order_id)
    ).scalar_one()
    assert item.quantity == Decimal("200.00")


@pytest.mark.asyncio
async def test_update_order_not_in_draft(auth_client: AsyncClient, setup_purchase_data: dict):
    """submitted 状态改单，预期 40901。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await auth_client.put(f"{ORDERS_PREFIX}/{order_id}", json=_create_order_payload(setup_purchase_data))
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非 draft 改单应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_delete_order_in_draft(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """draft 可删，is_deleted=1。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]

    resp = await auth_client.delete(f"{ORDERS_PREFIX}/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.is_deleted == 1, "删除后 is_deleted 应为1"


@pytest.mark.asyncio
async def test_delete_order_not_in_draft(auth_client: AsyncClient, setup_purchase_data: dict):
    """submitted 不可删，预期 40901。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await auth_client.delete(f"{ORDERS_PREFIX}/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非 draft 删单应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_order_no_format(auth_client: AsyncClient, setup_purchase_data: dict):
    """订单号符合 PO-YYYYMMDD-序号 格式。"""
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_no = order_data.json()["data"]["order_no"]
    parts = order_no.split("-")
    assert parts[0] == "PO", f"前缀应为PO，实际{parts[0]}"
    assert parts[1] == today, f"日期应为{today}，实际{parts[1]}"
    assert parts[2].isdigit(), f"序号应为数字，实际{parts[2]}"


# ===========================================================================
# 二、状态流转（7 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_submit_order(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """draft -> submitted。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]

    resp = await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.status == "submitted", "提交后状态应为 submitted"


@pytest.mark.asyncio
async def test_submit_order_not_in_draft(auth_client: AsyncClient, setup_purchase_data: dict):
    """非 draft 提交，预期 40901。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非 draft 提交应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_approve_order(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """submitted -> approved，approved_by 有值。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.status == "approved", "审核后状态应为 approved"
    assert order.approved_by is not None, "approved_by 应有值"


@pytest.mark.asyncio
async def test_approve_order_not_in_submitted(admin_client: AsyncClient, setup_purchase_data: dict):
    """非 submitted 审核，预期 40901。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    # draft 直接审核
    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非 submitted 审核应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_approve_twice(admin_client: AsyncClient, setup_purchase_data: dict):
    """重复审核，预期 40901。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"重复审核应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_cancel_order_in_draft(auth_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """draft 可取消。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]

    resp = await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.status == "cancelled", "取消后状态应为 cancelled"


@pytest.mark.asyncio
async def test_cancel_order_completed(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """completed 不可取消，预期 40901。"""
    # 创建订单 -> 审核 -> 入库全部收齐 -> completed
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")

    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "100"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]
    await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")

    resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"completed 不可取消: {resp.text}"


# ===========================================================================
# 三、采购入库单（10 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_create_in_from_approved_order(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """基于 approved 订单创建入库单，落库且状态 draft。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")

    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    assert in_data["status"] == "draft", "新建入库单状态应为 draft"

    pi = db_session.execute(select(PurchaseIn).where(PurchaseIn.id == in_data["id"])).scalar_one()
    assert pi.status == "draft"
    assert pi.total_quantity == Decimal("50.00")


@pytest.mark.asyncio
async def test_create_in_from_draft_order(auth_client: AsyncClient, setup_purchase_data: dict):
    """基于 draft 订单创建，预期 40901。"""
    order_data = await auth_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]

    resp = await auth_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"draft 订单不可创建入库单: {resp.text}"


@pytest.mark.asyncio
async def test_list_ins(admin_client: AsyncClient, setup_purchase_data: dict):
    """列表返回 200。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })

    resp = await admin_client.get(INS_PREFIX)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_get_in_detail(admin_client: AsyncClient, setup_purchase_data: dict):
    """详情含 items。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]

    resp = await admin_client.get(f"{INS_PREFIX}/{in_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == setup_purchase_data["product_id"]


@pytest.mark.asyncio
async def test_confirm_in_success(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """确认入库：status=confirmed，confirmed_by 有值，confirmed_at 有值。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]

    resp = await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    pi = db_session.execute(select(PurchaseIn).where(PurchaseIn.id == in_id)).scalar_one()
    assert pi.status == "confirmed"
    assert pi.confirmed_by is not None
    assert pi.confirmed_at is not None


@pytest.mark.asyncio
async def test_confirm_in_overflow(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """超收：确认时 received_quantity + 本次 > 订购数量，预期 40001，数据不变。

    通过创建两张入库单（60 + 50），先确认 60，再确认 50 时 60+50=110 > 100 触发超收。
    """
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")

    # 两张入库单：60 + 50，合计 110 > 100
    in1_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "60"}]
    })
    in1_id = in1_resp.json()["data"]["id"]
    in2_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    in2_id = in2_resp.json()["data"]["id"]

    # 先确认 60，成功
    await admin_client.post(f"{INS_PREFIX}/{in1_id}/confirm")

    # 确认 50 时超收，预期 40001
    resp = await admin_client.post(f"{INS_PREFIX}/{in2_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001, f"超收应返回40001: {resp.text}"

    # 订单 received_quantity 仍为 60（只有第一张入库成功）
    item = db_session.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.id == order_item_id)
    ).scalar_one()
    assert item.received_quantity == Decimal("60.00"), "超收时 received_quantity 不应增加"

    # 库存余额只有 60
    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == setup_purchase_data["product_id"],
            InventoryBalance.warehouse_id == setup_purchase_data["warehouse_id"],
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("60.00"), "超收时库存不应增加"

    # 流水只有 1 条（in1 的）
    movement_cnt = db_session.execute(
        select(func.count(StockMovement.id)).where(StockMovement.reference_type == "PURCHASE")
    ).scalar()
    assert movement_cnt == 1, "超收时不应写入第二条流水"


@pytest.mark.asyncio
async def test_confirm_in_twice(admin_client: AsyncClient, setup_purchase_data: dict):
    """重复确认，预期 40901。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]
    await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")

    resp = await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"重复确认应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_confirm_in_not_in_draft(admin_client: AsyncClient, setup_purchase_data: dict):
    """非 draft 确认（已取消），预期 40901。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]
    await admin_client.post(f"{INS_PREFIX}/{in_id}/cancel")

    resp = await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"非 draft 确认应返回40901: {resp.text}"


@pytest.mark.asyncio
async def test_partial_in_twice(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """两次分批入库合计=订购数，订单状态=completed。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")

    # 第一次入库 60
    in1_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "60"}]
    })
    await admin_client.post(f"{INS_PREFIX}/{in1_resp.json()['data']['id']}/confirm")

    # 订单应为 partial_in
    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.status == "partial_in", "部分入库后状态应为 partial_in"

    # 第二次入库 40
    in2_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "40"}]
    })
    await admin_client.post(f"{INS_PREFIX}/{in2_resp.json()['data']['id']}/confirm")

    # 订单应为 completed
    db_session.refresh(order)
    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.status == "completed", "全部入库后状态应为 completed"

    item = db_session.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.id == order_item_id)
    ).scalar_one()
    assert item.received_quantity == Decimal("100.00"), "已入库数量应等于订购数量"


@pytest.mark.asyncio
async def test_cancel_in_in_draft(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """draft 入库单可取消。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]

    resp = await admin_client.post(f"{INS_PREFIX}/{in_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    pi = db_session.execute(select(PurchaseIn).where(PurchaseIn.id == in_id)).scalar_one()
    assert pi.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_in_confirmed(admin_client: AsyncClient, setup_purchase_data: dict):
    """confirmed 入库单不可取消，预期 40901。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]
    await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")

    resp = await admin_client.post(f"{INS_PREFIX}/{in_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901, f"confirmed 不可取消: {resp.text}"


# ===========================================================================
# 四、库存联动与事务（6 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_confirm_in_updates_received_quantity(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """确认入库后 received_quantity 累加正确。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    await admin_client.post(f"{INS_PREFIX}/{in_data['id']}/confirm")

    item = db_session.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.id == order_item_id)
    ).scalar_one()
    assert item.received_quantity == Decimal("50.00"), "已入库数量应为50"


@pytest.mark.asyncio
async def test_confirm_in_updates_order_status_partial(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """未收齐 -> partial_in。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    await admin_client.post(f"{INS_PREFIX}/{in_data['id']}/confirm")

    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.status == "partial_in"


@pytest.mark.asyncio
async def test_confirm_in_updates_order_status_completed(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """收齐 -> completed。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "100"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    await admin_client.post(f"{INS_PREFIX}/{in_data['id']}/confirm")

    order = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id)).scalar_one()
    assert order.status == "completed"


@pytest.mark.asyncio
async def test_confirm_in_increases_inventory_balance(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """确认入库后库存余额增加量=入库量。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    pid = setup_purchase_data["product_id"]
    wid = setup_purchase_data["warehouse_id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    await admin_client.post(f"{INS_PREFIX}/{in_data['id']}/confirm")

    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid,
            InventoryBalance.warehouse_id == wid,
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("50.00"), "库存余额应增加50"


@pytest.mark.asyncio
async def test_confirm_in_creates_stock_movement(admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session):
    """确认入库后库存流水存在，字段正确。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]
    await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")

    movement = db_session.execute(
        select(StockMovement).where(
            StockMovement.reference_type == "PURCHASE",
            StockMovement.reference_id == in_id,
        )
    ).scalar_one()
    assert movement.movement_type == "IN"
    assert movement.quantity == Decimal("50.00")
    assert movement.reference_type == "PURCHASE"
    assert movement.reference_id == in_id


@pytest.mark.asyncio
async def test_confirm_in_atomicity(
    admin_client: AsyncClient, setup_purchase_data: dict, db_session: Session, monkeypatch
):
    """确认入库过程中 commit 抛异常，订单 received_quantity 不变、库存余额不变、无新流水。"""
    order_data = await admin_client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data, quantity="100"))
    order_id = order_data.json()["data"]["id"]
    order_item_id = order_data.json()["data"]["items"][0]["id"]
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/submit")
    await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/approve")
    in_resp = await admin_client.post(f"{ORDERS_PREFIX}/{order_id}/ins", json={
        "items": [{"purchase_order_item_id": order_item_id, "quantity": "50"}]
    })
    assert in_resp.status_code == 200
    in_data = in_resp.json()["data"]
    in_id = in_data["id"]

    # 记录确认前状态
    item_before = db_session.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.id == order_item_id)
    ).scalar_one()
    received_before = item_before.received_quantity

    # monkeypatch commit 抛异常
    def failing_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(RuntimeError):
        await admin_client.post(f"{INS_PREFIX}/{in_id}/confirm")

    monkeypatch.undo()
    db_session.rollback()

    # 订单 received_quantity 不变
    item_after = db_session.execute(
        select(PurchaseOrderItem).where(PurchaseOrderItem.id == order_item_id)
    ).scalar_one()
    assert item_after.received_quantity == received_before, "入库失败时 received_quantity 不应变化"

    # 库存余额不变
    balance_cnt = db_session.execute(select(func.count(InventoryBalance.id))).scalar()
    assert balance_cnt == 0, "入库失败时不应有库存余额"

    # 无新流水
    movement_cnt = db_session.execute(select(func.count(StockMovement.id))).scalar()
    assert movement_cnt == 0, "入库失败时不应有库存流水"


# ===========================================================================
# 五、鉴权（2 个）
# ===========================================================================


@pytest.mark.asyncio
async def test_create_order_without_token(client: AsyncClient, setup_purchase_data: dict):
    """无 Token 调用，预期 40101。"""
    resp = await client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    assert resp.status_code == 200
    assert resp.json()["code"] == 40101, "无 Token 应返回 40101"


@pytest.mark.asyncio
async def test_create_order_with_invalid_token(client: AsyncClient, setup_purchase_data: dict):
    """无效 Token 调用，预期 40101。"""
    client.headers["Authorization"] = "Bearer invalid.token.here"
    resp = await client.post(ORDERS_PREFIX, json=_create_order_payload(setup_purchase_data))
    assert resp.status_code == 200
    assert resp.json()["code"] == 40101, "无效 Token 应返回 40101"
