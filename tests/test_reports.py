"""报表模块测试。

覆盖库存流水汇总、低库存预警、采购/销售金额统计 4 个接口，
每个接口 2 个用例（有数据 + 无数据），共 8 个。
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from models.inventory import InventoryBalance
from models.product import Product
from models.supplier import Supplier

REPORTS_PREFIX = "/api/v1/reports"
INVENTORY_PREFIX = "/api/v1/inventory"
PURCHASE_ORDERS = "/api/v1/purchases/orders"
SALES_ORDERS = "/api/v1/sales/orders"


@pytest.fixture
def setup_report_data(db_session: Session, setup_basic_data: dict) -> dict:
    """在基础数据上创建供应商、客户，供采购/销售报表测试使用。"""
    from models.customer import Customer

    supplier = Supplier(code="SUP-RPT", name="报表供应商")
    customer = Customer(code="CUS-RPT", name="报表客户")
    db_session.add_all([supplier, customer])
    db_session.commit()
    db_session.refresh(supplier)
    db_session.refresh(customer)

    data = dict(setup_basic_data)
    data["supplier_id"] = supplier.id
    data["customer_id"] = customer.id
    return data


# ===========================================================================
# 接口 1：库存流水汇总
# ===========================================================================


@pytest.mark.asyncio
async def test_movements_report_with_data(auth_client: AsyncClient, setup_report_data: dict):
    """创建一条入库流水后，报表能查询到该记录。"""
    data = setup_report_data
    # 通过入库接口产生一条 IN 流水
    await auth_client.post(f"{INVENTORY_PREFIX}/in", json={
        "product_id": data["product_id"],
        "warehouse_id": data["warehouse_id"],
        "quantity": 100,
    })

    today = date.today().isoformat()
    resp = await auth_client.get(f"{REPORTS_PREFIX}/inventory-movements", params={
        "start_date": today,
        "end_date": today,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1
    assert body["data"]["page"] == 1
    items = body["data"]["items"]
    assert any(
        i["movement_type"] == "IN" and i["product_id"] == data["product_id"]
        for i in items
    )


@pytest.mark.asyncio
async def test_movements_report_empty(auth_client: AsyncClient, setup_report_data: dict):
    """无流水时返回空列表。"""
    resp = await auth_client.get(f"{REPORTS_PREFIX}/inventory-movements")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


# ===========================================================================
# 接口 2：低库存预警
# ===========================================================================


@pytest.mark.asyncio
async def test_low_stock_alerts_with_data(auth_client: AsyncClient, setup_report_data: dict, db_session: Session):
    """设置商品 min_stock=10 且库存=5 时，预警列表包含该商品。"""
    data = setup_report_data
    # 给基础商品设置预警阈值
    product = db_session.get(Product, data["product_id"])
    product.min_stock = 10
    db_session.commit()

    balance = InventoryBalance(
        product_id=data["product_id"],
        warehouse_id=data["warehouse_id"],
        current_quantity=5,
    )
    db_session.add(balance)
    db_session.commit()

    resp = await auth_client.get(f"{REPORTS_PREFIX}/low-stock-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1
    items = body["data"]["items"]
    match = next(
        (i for i in items if i["product_id"] == data["product_id"]), None
    )
    assert match is not None
    assert match["current_quantity"] == 5.0
    assert match["alert_threshold"] == 10.0


@pytest.mark.asyncio
async def test_low_stock_alerts_empty(auth_client: AsyncClient, setup_report_data: dict, db_session: Session):
    """库存充足时预警列表为空。"""
    data = setup_report_data
    balance = InventoryBalance(
        product_id=data["product_id"],
        warehouse_id=data["warehouse_id"],
        current_quantity=1000,
    )
    db_session.add(balance)
    db_session.commit()

    resp = await auth_client.get(f"{REPORTS_PREFIX}/low-stock-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["items"] == []


@pytest.mark.asyncio
async def test_low_stock_alerts_respects_min_stock(auth_client: AsyncClient, setup_report_data: dict, db_session: Session):
    """min_stock=5 时，库存=3 预警、库存=10 不预警。"""
    data = setup_report_data
    from models.category import Category
    from models.unit import Unit

    # 商品 A：min_stock=5，库存=3 → 预警
    category = db_session.get(Category, data["category_id"])
    unit = db_session.get(Unit, data["unit_id"])
    product_a = Product(
        sku="RPT-A", name="预警商品A", category_id=category.id,
        unit_id=unit.id, min_stock=5,
    )
    db_session.add(product_a)
    db_session.flush()
    # 商品 B：min_stock=5，库存=10 → 不预警
    product_b = Product(
        sku="RPT-B", name="不预警商品B", category_id=category.id,
        unit_id=unit.id, min_stock=5,
    )
    db_session.add(product_b)
    db_session.flush()

    db_session.add_all([
        InventoryBalance(product_id=product_a.id, warehouse_id=data["warehouse_id"], current_quantity=3),
        InventoryBalance(product_id=product_b.id, warehouse_id=data["warehouse_id"], current_quantity=10),
    ])
    db_session.commit()

    resp = await auth_client.get(f"{REPORTS_PREFIX}/low-stock-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    # 仅商品 A 命中预警
    assert body["data"]["total"] == 1
    assert items[0]["product_id"] == product_a.id
    assert items[0]["alert_threshold"] == 5.0


@pytest.mark.asyncio
async def test_low_stock_alerts_ignores_zero_min_stock(auth_client: AsyncClient, setup_report_data: dict, db_session: Session):
    """min_stock=0 或 NULL 的商品即使库存为 0 也不预警。"""
    data = setup_report_data
    from models.category import Category
    from models.unit import Unit

    category = db_session.get(Category, data["category_id"])
    unit = db_session.get(Unit, data["unit_id"])

    # 商品 C：min_stock=0，库存=0 → 不预警
    product_c = Product(
        sku="RPT-C", name="不预警商品C", category_id=category.id,
        unit_id=unit.id, min_stock=0,
    )
    db_session.add(product_c)
    db_session.flush()
    # 商品 D：min_stock=NULL，库存=0 → 不预警
    product_d = Product(
        sku="RPT-D", name="不预警商品D", category_id=category.id,
        unit_id=unit.id,
    )
    product_d.min_stock = None
    db_session.add(product_d)
    db_session.flush()

    db_session.add_all([
        InventoryBalance(product_id=product_c.id, warehouse_id=data["warehouse_id"], current_quantity=0),
        InventoryBalance(product_id=product_d.id, warehouse_id=data["warehouse_id"], current_quantity=0),
    ])
    db_session.commit()

    resp = await auth_client.get(f"{REPORTS_PREFIX}/low-stock-alerts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0


# ===========================================================================
# 接口 3：采购金额统计
# ===========================================================================


@pytest.mark.asyncio
async def test_purchase_summary_with_data(auth_client: AsyncClient, setup_report_data: dict):
    """创建采购订单后，统计结果包含该订单。"""
    data = setup_report_data
    # 创建一张采购订单（status=draft，报表统计所有非删除订单）
    await auth_client.post(PURCHASE_ORDERS, json={
        "supplier_id": data["supplier_id"],
        "warehouse_id": data["warehouse_id"],
        "items": [{"product_id": data["product_id"], "quantity": "100", "unit_price": "10.00"}],
    })

    today = date.today().isoformat()
    resp = await auth_client.get(f"{REPORTS_PREFIX}/purchase-summary", params={
        "start_date": today,
        "end_date": today,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    d = body["data"]
    assert d["total_orders"] == 1
    assert d["total_items"] == 1
    assert d["total_amount"] == 1000.0
    assert d["total_quantity"] == 100.0
    assert len(d["by_supplier"]) == 1
    assert d["by_supplier"][0]["supplier_id"] == data["supplier_id"]
    assert d["by_supplier"][0]["total_amount"] == 1000.0


@pytest.mark.asyncio
async def test_purchase_summary_no_data(auth_client: AsyncClient, setup_report_data: dict):
    """无采购订单时统计结果全为 0。"""
    resp = await auth_client.get(f"{REPORTS_PREFIX}/purchase-summary", params={
        "start_date": "2000-01-01",
        "end_date": "2000-01-02",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    d = body["data"]
    assert d["total_orders"] == 0
    assert d["total_amount"] == 0
    assert d["by_supplier"] == []


# ===========================================================================
# 接口 4：销售金额统计
# ===========================================================================


@pytest.mark.asyncio
async def test_sales_summary_with_data(auth_client: AsyncClient, setup_report_data: dict):
    """创建销售订单后，统计结果包含该订单。"""
    data = setup_report_data
    await auth_client.post(SALES_ORDERS, json={
        "customer_id": data["customer_id"],
        "warehouse_id": data["warehouse_id"],
        "items": [{"product_id": data["product_id"], "quantity": "60", "unit_price": "15.00"}],
    })

    today = date.today().isoformat()
    resp = await auth_client.get(f"{REPORTS_PREFIX}/sales-summary", params={
        "start_date": today,
        "end_date": today,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    d = body["data"]
    assert d["total_orders"] == 1
    assert d["total_items"] == 1
    assert d["total_amount"] == 900.0
    assert d["total_quantity"] == 60.0
    assert len(d["by_customer"]) == 1
    assert d["by_customer"][0]["customer_id"] == data["customer_id"]
    assert d["by_customer"][0]["total_amount"] == 900.0


@pytest.mark.asyncio
async def test_sales_summary_no_data(auth_client: AsyncClient, setup_report_data: dict):
    """无销售订单时统计结果全为 0。"""
    resp = await auth_client.get(f"{REPORTS_PREFIX}/sales-summary", params={
        "start_date": "2000-01-01",
        "end_date": "2000-01-02",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    d = body["data"]
    assert d["total_orders"] == 0
    assert d["total_amount"] == 0
    assert d["by_customer"] == []
