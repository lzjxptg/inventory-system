"""库存模块单元测试。

覆盖入库、出库、盘点调整、余额/流水查询、事务一致性、鉴权等场景。
所有测试在独立事务中运行，结束后自动回滚。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.inventory import InventoryBalance, StockMovement

INVENTORY_PREFIX = "/api/v1/inventory"


# ===========================================================================
# 一、入库
# ===========================================================================


@pytest.mark.asyncio
async def test_stock_in_success(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """正常入库：余额增加，流水新增 IN 记录。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100, "remark": "初始入库"},
    )
    assert resp.status_code == 200, f"入库接口返回异常: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"业务码应为0: {body}"

    # 查数据库核对余额
    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("100.00"), "入库后余额应为100"

    # 查数据库核对流水
    movement = db_session.execute(
        select(StockMovement).where(
            StockMovement.product_id == pid,
            StockMovement.warehouse_id == wid,
            StockMovement.movement_type == "IN",
        )
    ).scalar_one()
    assert movement.quantity == Decimal("100.00"), "流水数量应与请求一致"


@pytest.mark.asyncio
async def test_stock_in_negative_quantity(auth_client: AsyncClient, setup_basic_data: dict):
    """入库数量为负数，预期 422。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": -50},
    )
    assert resp.status_code == 422, f"负数数量应返回422，实际: {resp.status_code}"


@pytest.mark.asyncio
async def test_stock_in_zero_quantity(auth_client: AsyncClient, setup_basic_data: dict):
    """入库数量为 0，预期 422。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 0},
    )
    assert resp.status_code == 422, f"数量为0应返回422，实际: {resp.status_code}"


@pytest.mark.asyncio
async def test_stock_in_nonexistent_product(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """商品不存在，预期 400，且余额/流水表无变化。"""
    wid = setup_basic_data["warehouse_id"]

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": 999999, "warehouse_id": wid, "quantity": 100},
    )
    assert resp.status_code == 200, f"不存在商品应返回200，实际: {resp.status_code}"
    assert resp.json()["code"] == 40001, f"不存在商品应返回业务码40001: {resp.text}"
    assert "商品" in resp.json()["msg"], f"错误信息应包含商品: {resp.text}"

    # 余额表不应有记录
    cnt = db_session.execute(select(func.count(InventoryBalance.id))).scalar()
    assert cnt == 0, "商品不存在时不应写入余额表"

    # 流水表不应有记录
    cnt = db_session.execute(select(func.count(StockMovement.id))).scalar()
    assert cnt == 0, "商品不存在时不应写入流水表"


# ===========================================================================
# 二、出库
# ===========================================================================


@pytest.mark.asyncio
async def test_stock_out_success(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """先入库100再出库30，余额变为70，流水新增 OUT 记录。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    # 入库 100
    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    # 出库 30
    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/out",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 30},
    )
    assert resp.status_code == 200, f"出库接口返回异常: {resp.text}"
    assert resp.json()["code"] == 0

    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("70.00"), "出库后余额应为70"

    movement = db_session.execute(
        select(StockMovement).where(
            StockMovement.product_id == pid,
            StockMovement.warehouse_id == wid,
            StockMovement.movement_type == "OUT",
        )
    ).scalar_one()
    assert movement.quantity == Decimal("-30.00"), "出库流水数量应为-30"


@pytest.mark.asyncio
async def test_stock_out_overflow(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """库存不足时出库，预期 400，余额与流水均无变化。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    # 入库 100
    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    # 出库 200（超出库存）
    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/out",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 200},
    )
    assert resp.status_code == 200, f"库存不足应返回200，实际: {resp.status_code}"
    assert resp.json()["code"] == 40001, f"库存不足应返回业务码40001: {resp.text}"
    assert "库存" in resp.json()["msg"], f"错误信息应包含库存: {resp.text}"

    # 余额不变
    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("100.00"), "库存不足时余额不应变化"

    # 流水只有入库一条
    cnt = db_session.execute(
        select(func.count(StockMovement.id)).where(StockMovement.movement_type == "OUT")
    ).scalar()
    assert cnt == 0, "库存不足时不应写入出库流水"


@pytest.mark.asyncio
async def test_stock_out_negative_quantity(auth_client: AsyncClient, setup_basic_data: dict):
    """出库数量为负，预期 422。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/out",
        json={"product_id": pid, "warehouse_id": wid, "quantity": -30},
    )
    assert resp.status_code == 422, f"负数数量应返回422，实际: {resp.status_code}"


@pytest.mark.asyncio
async def test_stock_out_zero_quantity(auth_client: AsyncClient, setup_basic_data: dict):
    """出库数量为 0，预期 422。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/out",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 0},
    )
    assert resp.status_code == 422, f"数量为0应返回422，实际: {resp.status_code}"


# ===========================================================================
# 三、盘点调整
# ===========================================================================


@pytest.mark.asyncio
async def test_adjust_increase(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """余额100调整到120，余额变为120，流水 ADJUST 差值为正。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/adjust",
        json={"product_id": pid, "warehouse_id": wid, "new_quantity": 120},
    )
    assert resp.status_code == 200, f"调整接口返回异常: {resp.text}"
    assert resp.json()["code"] == 0

    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("120.00"), "调整后余额应为120"

    movement = db_session.execute(
        select(StockMovement).where(
            StockMovement.product_id == pid,
            StockMovement.warehouse_id == wid,
            StockMovement.movement_type == "ADJUST",
        )
    ).scalar_one()
    assert movement.quantity == Decimal("20.00"), "盘盈流水差值应为+20"


@pytest.mark.asyncio
async def test_adjust_decrease(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """余额120调整到90，余额变为90，流水差值为负。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )
    await auth_client.post(
        f"{INVENTORY_PREFIX}/adjust",
        json={"product_id": pid, "warehouse_id": wid, "new_quantity": 120},
    )

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/adjust",
        json={"product_id": pid, "warehouse_id": wid, "new_quantity": 90},
    )
    assert resp.status_code == 200, f"调整接口返回异常: {resp.text}"

    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("90.00"), "调整后余额应为90"

    # 取最近一条 ADJUST 流水
    movements = db_session.execute(
        select(StockMovement).where(
            StockMovement.product_id == pid,
            StockMovement.warehouse_id == wid,
            StockMovement.movement_type == "ADJUST",
        )
    ).scalars().all()
    latest = max(movements, key=lambda m: m.id)
    assert latest.quantity == Decimal("-30.00"), "盘亏流水差值应为-30"


@pytest.mark.asyncio
async def test_adjust_to_zero(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """调整使余额归零，不报错，余额为0。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/adjust",
        json={"product_id": pid, "warehouse_id": wid, "new_quantity": 0},
    )
    assert resp.status_code == 200, f"归零调整不应报错: {resp.text}"
    assert resp.json()["code"] == 0

    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("0.00"), "调整后余额应为0"


@pytest.mark.asyncio
async def test_adjust_below_zero(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """调整为负数被 schema 拦截（new_quantity ge=0），返回422，数据不变。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    resp = await auth_client.post(
        f"{INVENTORY_PREFIX}/adjust",
        json={"product_id": pid, "warehouse_id": wid, "new_quantity": -20},
    )
    assert resp.status_code == 422, f"负数盘点应返回422，实际: {resp.status_code}"

    # 余额不变
    balance = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one()
    assert balance.current_quantity == Decimal("100.00"), "调整失败时余额不应变化"


# ===========================================================================
# 四、余额与流水查询
# ===========================================================================


@pytest.mark.asyncio
async def test_get_balances_empty(auth_client: AsyncClient):
    """无库存数据时返回空列表。"""
    resp = await auth_client.get(f"{INVENTORY_PREFIX}/balances")
    assert resp.status_code == 200
    assert resp.json()["data"] == [], "无数据时余额列表应为空"


@pytest.mark.asyncio
async def test_get_balances_after_in(auth_client: AsyncClient, setup_basic_data: dict):
    """入库后查询余额列表，条数和数量正确。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    resp = await auth_client.get(f"{INVENTORY_PREFIX}/balances")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1, f"应有1条余额记录，实际{len(data)}"
    assert data[0]["current_quantity"] == 100.0, "余额数量应为100"


@pytest.mark.asyncio
async def test_get_single_balance(auth_client: AsyncClient, setup_basic_data: dict):
    """按 product_id/warehouse_id 查询单条余额，字段完整。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    resp = await auth_client.get(f"{INVENTORY_PREFIX}/balances/{pid}/{wid}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["product_id"] == pid, "product_id 不匹配"
    assert data["warehouse_id"] == wid, "warehouse_id 不匹配"
    assert data["current_quantity"] == 100.0, "current_quantity 应为100"
    assert data["product_name"] == "测试商品", "product_name 应为测试商品"
    assert data["warehouse_name"] == "测试仓库", "warehouse_name 应为测试仓库"


@pytest.mark.asyncio
async def test_get_single_balance_not_found(auth_client: AsyncClient):
    """查询不存在商品的余额，预期返回 404 业务码。"""
    resp = await auth_client.get(f"{INVENTORY_PREFIX}/balances/999999/999999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 404, "不存在的余额应返回业务码404"


@pytest.mark.asyncio
async def test_get_movements(auth_client: AsyncClient, setup_basic_data: dict, db_session: Session):
    """入库、出库、调整各一次后查流水，共3条且按 id 倒序。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )
    await auth_client.post(
        f"{INVENTORY_PREFIX}/out",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 30},
    )
    await auth_client.post(
        f"{INVENTORY_PREFIX}/adjust",
        json={"product_id": pid, "warehouse_id": wid, "new_quantity": 80},
    )

    resp = await auth_client.get(f"{INVENTORY_PREFIX}/movements")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 3, f"应有3条流水，实际{len(data)}"

    # 验证倒序：id 递减
    ids = [m["id"] for m in data]
    assert ids == sorted(ids, reverse=True), "流水应按 id 倒序排列"

    # 验证三种类型都存在
    types = {m["movement_type"] for m in data}
    assert types == {"IN", "OUT", "ADJUST"}, f"流水类型应为IN/OUT/ADJUST，实际{types}"


@pytest.mark.asyncio
async def test_get_movements_filter_by_product(auth_client: AsyncClient, setup_basic_data: dict):
    """按 product_id 过滤流水，只返回该商品的记录。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    resp = await auth_client.get(f"{INVENTORY_PREFIX}/movements", params={"product_id": pid})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1, f"过滤后应有1条流水，实际{len(data)}"
    assert data[0]["product_id"] == pid, "过滤结果 product_id 不匹配"

    # 用不存在的 product_id 过滤，应为空
    resp2 = await auth_client.get(
        f"{INVENTORY_PREFIX}/movements", params={"product_id": 999999}
    )
    assert resp2.json()["data"] == [], "不存在商品的流水应为空"


# ===========================================================================
# 五、事务一致性
# ===========================================================================


@pytest.mark.asyncio
async def test_in_out_atomicity(
    auth_client: AsyncClient, setup_basic_data: dict, db_session: Session, monkeypatch
):
    """出库过程中 commit 抛异常，余额与流水均无变化（事务回滚）。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    # 先入库 100
    await auth_client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )

    # 记录出库前余额
    balance_before = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one().current_quantity

    # monkeypatch session.commit 抛异常，模拟出库过程中断
    def failing_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    # 尝试出库，异常会从 ASGI app 逃逸（ASGITransport 传播未处理异常）
    with pytest.raises(RuntimeError):
        await auth_client.post(
            f"{INVENTORY_PREFIX}/out",
            json={"product_id": pid, "warehouse_id": wid, "quantity": 30},
        )

    # 恢复 commit 并回滚 session，丢弃未提交的内存变更
    monkeypatch.undo()
    db_session.rollback()

    # 余额不变
    balance_after = db_session.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar_one().current_quantity
    assert balance_after == balance_before, "出库失败时余额不应变化"

    # 流水只有入库一条，无出库记录
    out_cnt = db_session.execute(
        select(func.count(StockMovement.id)).where(StockMovement.movement_type == "OUT")
    ).scalar()
    assert out_cnt == 0, "出库失败时不应写入流水"


@pytest.mark.asyncio
async def test_duplicate_balance_unique_constraint(setup_basic_data: dict, db_session: Session):
    """同一 product_id+warehouse_id 重复插入余额，触发唯一约束报错，已有数据不受影响。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    # 第一条余额
    balance1 = InventoryBalance(
        product_id=pid, warehouse_id=wid, current_quantity=Decimal("100.00")
    )
    db_session.add(balance1)
    db_session.commit()

    # 第二条同 key 余额，应触发唯一约束
    balance2 = InventoryBalance(
        product_id=pid, warehouse_id=wid, current_quantity=Decimal("200.00")
    )
    db_session.add(balance2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    # 回滚后查询，应只有一条余额记录
    db_session.rollback()
    cnt = db_session.execute(
        select(func.count(InventoryBalance.id)).where(
            InventoryBalance.product_id == pid, InventoryBalance.warehouse_id == wid
        )
    ).scalar()
    assert cnt == 1, "唯一约束冲突后应只保留一条余额记录"


# ===========================================================================
# 六、鉴权
# ===========================================================================


@pytest.mark.asyncio
async def test_inventory_endpoints_without_token(client: AsyncClient, setup_basic_data: dict):
    """不带 Token 调用入库接口，预期业务码 40101。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    resp = await client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40101, "无 Token 应返回 40101"


@pytest.mark.asyncio
async def test_inventory_endpoints_with_invalid_token(client: AsyncClient, setup_basic_data: dict):
    """带无效 Token 调用入库接口，预期业务码 40101。"""
    pid = setup_basic_data["product_id"]
    wid = setup_basic_data["warehouse_id"]

    client.headers["Authorization"] = "Bearer invalid.token.here"
    resp = await client.post(
        f"{INVENTORY_PREFIX}/in",
        json={"product_id": pid, "warehouse_id": wid, "quantity": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40101, "无效 Token 应返回 40101"
