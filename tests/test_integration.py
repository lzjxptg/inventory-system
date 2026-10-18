"""跨模块端到端集成测试。

串联 采购入库 → 库存 → 销售出库 核心三角，验证数据一致性。
只新增本文件，不改任何业务代码、路由、crud、迁移和现有测试。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.customer import Customer
from models.inventory import InventoryBalance, StockMovement
from models.purchase import PurchaseOrder, PurchaseIn
from models.sales import SalesOrder, SalesOut
from models.supplier import Supplier

PURCHASE_ORDERS = "/api/v1/purchases/orders"
PURCHASE_INS = "/api/v1/purchases/ins"
SALES_ORDERS = "/api/v1/sales/orders"
SALES_OUTS = "/api/v1/sales/outs"


# ---------------------------------------------------------------------------
# 基础数据 fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_e2e_data(db_session: Session, setup_basic_data: dict) -> dict:
    """在 setup_basic_data 基础上创建供应商和客户。"""
    supplier = Supplier(code="SUP-E2E", name="E2E供应商")
    customer = Customer(code="CUS-E2E", name="E2E客户")
    db_session.add(supplier)
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(supplier)
    db_session.refresh(customer)

    data = dict(setup_basic_data)
    data["supplier_id"] = supplier.id
    data["customer_id"] = customer.id
    return data


def _balance(db: Session, product_id: int, warehouse_id: int) -> Decimal:
    """读取库存余额，不存在返回 0。"""
    b = db.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == product_id,
            InventoryBalance.warehouse_id == warehouse_id,
        )
    ).scalar_one_or_none()
    return b.current_quantity if b else Decimal("0")


# ===========================================================================
# 用例 1：采购入库 → 库存 → 销售出库 完整闭环
# ===========================================================================


@pytest.mark.asyncio
async def test_e2e_purchase_to_sale(auth_client: AsyncClient, setup_e2e_data: dict, db_session: Session):
    """核心闭环：采购 100 入库 → 销售 60 出库，验证库存与流水一致性。"""
    pid = setup_e2e_data["product_id"]
    wid = setup_e2e_data["warehouse_id"]
    sid = setup_e2e_data["supplier_id"]
    cid = setup_e2e_data["customer_id"]

    # ---- Step 2: 创建采购订单 ----
    r = await auth_client.post(PURCHASE_ORDERS, json={
        "supplier_id": sid,
        "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": "100", "unit_price": "10.00"}],
    })
    assert r.status_code == 200, "Step 2 创建采购订单应返回 200"
    assert r.json()["code"] == 0, "Step 2 采购订单业务码应为 0"
    po_id = r.json()["data"]["id"]
    po_item_id = r.json()["data"]["items"][0]["id"]
    assert r.json()["data"]["status"] == "draft", "Step 2 新建采购订单应为 draft"

    # ---- Step 3: 提交并审核采购订单 ----
    r = await auth_client.post(f"{PURCHASE_ORDERS}/{po_id}/submit")
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 3 提交采购订单失败"
    r = await auth_client.post(f"{PURCHASE_ORDERS}/{po_id}/approve")
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 3 审核采购订单失败"

    # ---- Step 4: 创建并确认采购入库单 ----
    r = await auth_client.post(f"{PURCHASE_ORDERS}/{po_id}/ins", json={
        "items": [{"purchase_order_item_id": po_item_id, "quantity": "100",
                   "unit_price": "10.00", "batch_no": "E2E-BATCH-001"}],
    })
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 4 创建入库单失败"
    in_id = r.json()["data"]["id"]
    r = await auth_client.post(f"{PURCHASE_INS}/{in_id}/confirm")
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 4 确认入库单失败"

    po = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id)).scalar_one()
    assert po.status == "completed", "Step 4 采购订单应收齐为 completed"
    pi = db_session.execute(select(PurchaseIn).where(PurchaseIn.id == in_id)).scalar_one()
    assert pi.status == "confirmed", "Step 4 入库单应为 confirmed"

    # ---- Step 5: 验证库存增加 ----
    assert _balance(db_session, pid, wid) == Decimal("100.00"), "Step 5 入库后库存应为 100"
    mv_in = db_session.execute(
        select(StockMovement).where(
            StockMovement.movement_type == "IN",
            StockMovement.reference_type == "PURCHASE",
            StockMovement.reference_id == in_id,
        )
    ).scalar_one_or_none()
    assert mv_in is not None, "Step 5 应存在采购入库流水"
    assert mv_in.quantity == Decimal("100.00"), "Step 5 入库流水数量应为 100"

    # ---- Step 6: 创建销售订单 ----
    r = await auth_client.post(SALES_ORDERS, json={
        "customer_id": cid,
        "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": "60", "unit_price": "15.00"}],
    })
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 6 创建销售订单失败"
    so_id = r.json()["data"]["id"]
    so_item_id = r.json()["data"]["items"][0]["id"]
    assert r.json()["data"]["status"] == "draft", "Step 6 新建销售订单应为 draft"

    # ---- Step 7: 提交并审核销售订单 ----
    r = await auth_client.post(f"{SALES_ORDERS}/{so_id}/submit")
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 7 提交销售订单失败"
    r = await auth_client.post(f"{SALES_ORDERS}/{so_id}/approve")
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 7 审核销售订单失败"

    # ---- Step 8: 创建并确认销售出库单 ----
    r = await auth_client.post(f"{SALES_ORDERS}/{so_id}/outs", json={
        "items": [{"sales_order_item_id": so_item_id, "quantity": "60",
                   "unit_price": "15.00", "batch_no": "E2E-OUT-001"}],
    })
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 8 创建出库单失败"
    out_id = r.json()["data"]["id"]
    r = await auth_client.post(f"{SALES_OUTS}/{out_id}/confirm")
    assert r.status_code == 200 and r.json()["code"] == 0, "Step 8 确认出库单失败"

    so = db_session.execute(select(SalesOrder).where(SalesOrder.id == so_id)).scalar_one()
    assert so.status == "completed", "Step 8 销售订单应全部出库为 completed"
    sout = db_session.execute(select(SalesOut).where(SalesOut.id == out_id)).scalar_one()
    assert sout.status == "confirmed", "Step 8 出库单应为 confirmed"

    # ---- Step 9: 验证库存减少 ----
    assert _balance(db_session, pid, wid) == Decimal("40.00"), "Step 9 出库后库存应为 40"
    mv_out = db_session.execute(
        select(StockMovement).where(
            StockMovement.movement_type == "OUT",
            StockMovement.reference_type == "SALE",
            StockMovement.reference_id == out_id,
        )
    ).scalar_one_or_none()
    assert mv_out is not None, "Step 9 应存在销售出库流水"
    assert mv_out.quantity == Decimal("-60.00"), "Step 9 出库流水数量应为 -60"

    # ---- Step 10: 流水完整性 ----
    mvs = db_session.execute(
        select(StockMovement).where(
            StockMovement.product_id == pid,
            StockMovement.warehouse_id == wid,
        )
    ).scalars().all()
    assert len(mvs) == 2, "Step 10 应仅有 2 条流水（1 IN + 1 OUT）"
    total = sum((m.quantity for m in mvs), Decimal("0"))
    assert total == Decimal("40.00"), "Step 10 流水合计应等于库存余额 40"

    # ---- Step 11: 金额独立 ----
    assert po.total_amount == Decimal("1000.00"), "Step 11 采购金额应为 100×10=1000"
    assert so.total_amount == Decimal("900.00"), "Step 11 销售金额应为 60×15=900"
    assert po.total_amount != so.total_amount, "Step 11 采购与销售金额应独立计算"


# ===========================================================================
# 用例 2：分批入库后部分出库
# ===========================================================================


@pytest.mark.asyncio
async def test_e2e_partial_purchase_then_sale(auth_client: AsyncClient, setup_e2e_data: dict, db_session: Session):
    """采购 50 分批入库（30 + 20）→ 销售 20 出库，验证最终库存 30、流水 3 条。"""
    pid = setup_e2e_data["product_id"]
    wid = setup_e2e_data["warehouse_id"]
    sid = setup_e2e_data["supplier_id"]
    cid = setup_e2e_data["customer_id"]

    # 采购订单 50
    r = await auth_client.post(PURCHASE_ORDERS, json={
        "supplier_id": sid, "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": "50", "unit_price": "8.00"}],
    })
    po_id = r.json()["data"]["id"]
    po_item_id = r.json()["data"]["items"][0]["id"]
    await auth_client.post(f"{PURCHASE_ORDERS}/{po_id}/submit")
    await auth_client.post(f"{PURCHASE_ORDERS}/{po_id}/approve")

    # 分批入库：30 + 20
    r1 = await auth_client.post(f"{PURCHASE_ORDERS}/{po_id}/ins", json={
        "items": [{"purchase_order_item_id": po_item_id, "quantity": "30", "unit_price": "8.00"}],
    })
    await auth_client.post(f"{PURCHASE_INS}/{r1.json()['data']['id']}/confirm")
    r2 = await auth_client.post(f"{PURCHASE_ORDERS}/{po_id}/ins", json={
        "items": [{"purchase_order_item_id": po_item_id, "quantity": "20", "unit_price": "8.00"}],
    })
    await auth_client.post(f"{PURCHASE_INS}/{r2.json()['data']['id']}/confirm")

    po = db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id)).scalar_one()
    assert po.status == "completed", "分批入库完成后采购订单应为 completed"
    assert _balance(db_session, pid, wid) == Decimal("50.00"), "两次入库后库存应为 50"

    # 销售 20 出库
    r = await auth_client.post(SALES_ORDERS, json={
        "customer_id": cid, "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": "20", "unit_price": "12.00"}],
    })
    so_id = r.json()["data"]["id"]
    so_item_id = r.json()["data"]["items"][0]["id"]
    await auth_client.post(f"{SALES_ORDERS}/{so_id}/submit")
    await auth_client.post(f"{SALES_ORDERS}/{so_id}/approve")

    r = await auth_client.post(f"{SALES_ORDERS}/{so_id}/outs", json={
        "items": [{"sales_order_item_id": so_item_id, "quantity": "20", "unit_price": "12.00"}],
    })
    out_id = r.json()["data"]["id"]
    await auth_client.post(f"{SALES_OUTS}/{out_id}/confirm")

    so = db_session.execute(select(SalesOrder).where(SalesOrder.id == so_id)).scalar_one()
    assert so.status == "completed", "销售出库完成后订单应为 completed"

    # 最终库存 30
    assert _balance(db_session, pid, wid) == Decimal("30.00"), "最终库存应为 50-20=30"

    # 流水共 3 条（2 IN + 1 OUT）
    mvs = db_session.execute(
        select(StockMovement).where(
            StockMovement.product_id == pid,
            StockMovement.warehouse_id == wid,
        )
    ).scalars().all()
    assert len(mvs) == 3, "应共有 3 条流水（2 IN + 1 OUT）"
    in_count = sum(1 for m in mvs if m.movement_type == "IN")
    out_count = sum(1 for m in mvs if m.movement_type == "OUT")
    assert in_count == 2 and out_count == 1, "应有 2 条 IN 和 1 条 OUT 流水"


# ===========================================================================
# 用例 3：库存不足拦截闭环验证
# ===========================================================================


@pytest.mark.asyncio
async def test_e2e_insufficient_stock_blocks_sale(auth_client: AsyncClient, setup_e2e_data: dict, db_session: Session):
    """不采购直接销售出库，验证超卖拦截、库存不变、无 OUT 流水。"""
    pid = setup_e2e_data["product_id"]
    wid = setup_e2e_data["warehouse_id"]
    cid = setup_e2e_data["customer_id"]

    # 确认初始库存为 0
    assert _balance(db_session, pid, wid) == Decimal("0"), "初始库存应为 0"

    # 创建并审核销售订单
    r = await auth_client.post(SALES_ORDERS, json={
        "customer_id": cid, "warehouse_id": wid,
        "items": [{"product_id": pid, "quantity": "50", "unit_price": "15.00"}],
    })
    so_id = r.json()["data"]["id"]
    so_item_id = r.json()["data"]["items"][0]["id"]
    await auth_client.post(f"{SALES_ORDERS}/{so_id}/submit")
    await auth_client.post(f"{SALES_ORDERS}/{so_id}/approve")

    # 创建出库单
    r = await auth_client.post(f"{SALES_ORDERS}/{so_id}/outs", json={
        "items": [{"sales_order_item_id": so_item_id, "quantity": "50", "unit_price": "15.00"}],
    })
    out_id = r.json()["data"]["id"]

    # 确认出库应被超卖拦截
    r = await auth_client.post(f"{SALES_OUTS}/{out_id}/confirm")
    assert r.status_code == 200, "确认出库请求应返回 200"
    assert r.json()["code"] == 40001, f"库存不足应返回 40001，实际: {r.text}"

    # 库存余额不变（仍为 0）
    assert _balance(db_session, pid, wid) == Decimal("0"), "超卖拦截后库存余额应仍为 0"

    # 无 OUT 流水
    out_cnt = db_session.execute(
        select(func.count(StockMovement.id)).where(
            StockMovement.movement_type == "OUT",
            StockMovement.reference_type == "SALE",
        )
    ).scalar()
    assert out_cnt == 0, "超卖拦截后不应产生 OUT 流水"

    # 销售订单状态不应为 completed
    so = db_session.execute(select(SalesOrder).where(SalesOrder.id == so_id)).scalar_one()
    assert so.status == "approved", "出库失败后销售订单应仍为 approved"
