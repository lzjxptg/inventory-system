"""报表查询逻辑（只读）。

提供库存流水汇总、低库存预警、采购/销售金额统计四类查询。
所有函数只读取数据库，不写入、不提交事务。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.customer import Customer
from models.inventory import InventoryBalance, StockMovement
from models.product import Product
from models.purchase import PurchaseOrder, PurchaseOrderItem
from models.sales import SalesOrder, SalesOrderItem
from models.supplier import Supplier
from models.warehouse import Warehouse


# ---------------------------------------------------------------------------
# 接口 1：库存流水汇总
# ---------------------------------------------------------------------------


def get_movements_report(
    db: Session,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    movement_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """库存流水汇总查询（带筛选与分页）。"""
    stmt = (
        select(StockMovement)
        .join(Product, StockMovement.product_id == Product.id)
        .join(Warehouse, StockMovement.warehouse_id == Warehouse.id)
        .where(StockMovement.is_deleted == 0)
        .order_by(StockMovement.created_at.desc())
    )
    count_stmt = select(func.count(StockMovement.id)).where(StockMovement.is_deleted == 0)

    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
        count_stmt = count_stmt.where(StockMovement.product_id == product_id)
    if warehouse_id is not None:
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
        count_stmt = count_stmt.where(StockMovement.warehouse_id == warehouse_id)
    if movement_type is not None:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
        count_stmt = count_stmt.where(StockMovement.movement_type == movement_type)
    if start_date is not None:
        stmt = stmt.where(func.date(StockMovement.created_at) >= start_date)
        count_stmt = count_stmt.where(func.date(StockMovement.created_at) >= start_date)
    if end_date is not None:
        stmt = stmt.where(func.date(StockMovement.created_at) <= end_date)
        count_stmt = count_stmt.where(func.date(StockMovement.created_at) <= end_date)

    total = db.execute(count_stmt).scalar() or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# 接口 2：低库存预警
# ---------------------------------------------------------------------------


def get_low_stock_alerts(
    db: Session,
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """低库存预警：仅预警 min_stock > 0 且 current_quantity <= min_stock 的商品。

    min_stock = 0 或 NULL 的商品不参与预警（业务含义为不关注库存下限）。
    """
    alert_filter = (
        Product.min_stock.isnot(None)
        & (Product.min_stock > 0)
        & (InventoryBalance.current_quantity <= Product.min_stock)
    )

    stmt = (
        select(InventoryBalance)
        .join(Product, InventoryBalance.product_id == Product.id)
        .join(Warehouse, InventoryBalance.warehouse_id == Warehouse.id)
        .where(InventoryBalance.is_deleted == 0, alert_filter)
        .order_by(InventoryBalance.current_quantity.asc())
    )
    count_stmt = (
        select(func.count(InventoryBalance.id))
        .join(Product, InventoryBalance.product_id == Product.id)
        .where(InventoryBalance.is_deleted == 0, alert_filter)
    )

    if warehouse_id is not None:
        stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
        count_stmt = count_stmt.where(InventoryBalance.warehouse_id == warehouse_id)

    total = db.execute(count_stmt).scalar() or 0
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars().all()
    return {
        "items": [
            {
                "product_id": b.product_id,
                "product_name": b.product_name,
                "warehouse_id": b.warehouse_id,
                "warehouse_name": b.warehouse_name,
                "current_quantity": b.current_quantity,
                "alert_threshold": b.product.min_stock,
            }
            for b in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# 接口 3：采购金额统计
# ---------------------------------------------------------------------------


def get_purchase_summary(
    db: Session,
    start_date: date,
    end_date: date,
    supplier_id: int | None = None,
) -> dict:
    """采购金额统计：指定日期范围内的订单数、明细数、总金额、总数量、按供应商分组。"""
    order_filter = [
        PurchaseOrder.is_deleted == 0,
        func.date(PurchaseOrder.created_at) >= start_date,
        func.date(PurchaseOrder.created_at) <= end_date,
    ]
    if supplier_id is not None:
        order_filter.append(PurchaseOrder.supplier_id == supplier_id)

    # 订单总数与金额/数量汇总
    order_agg = db.execute(
        select(
            func.count(PurchaseOrder.id),
            func.coalesce(func.sum(PurchaseOrder.total_amount), 0),
            func.coalesce(func.sum(PurchaseOrder.total_quantity), 0),
        ).where(*order_filter)
    ).one()
    total_orders = order_agg[0] or 0
    total_amount = order_agg[1] or Decimal("0")
    total_quantity = order_agg[2] or Decimal("0")

    # 明细总数：关联订单的明细条数
    item_count = db.execute(
        select(func.count(PurchaseOrderItem.id))
        .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
        .where(*order_filter)
    ).scalar() or 0

    # 按供应商分组
    by_supplier_stmt = (
        select(
            PurchaseOrder.supplier_id,
            Supplier.name,
            func.count(PurchaseOrder.id),
            func.coalesce(func.sum(PurchaseOrder.total_amount), 0),
        )
        .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        .where(*order_filter)
        .group_by(PurchaseOrder.supplier_id, Supplier.name)
    )
    by_supplier_rows = db.execute(by_supplier_stmt).all()
    by_supplier = [
        {
            "supplier_id": row[0],
            "supplier_name": row[1] or "",
            "order_count": row[2],
            "total_amount": row[3] or Decimal("0"),
        }
        for row in by_supplier_rows
    ]

    return {
        "total_orders": total_orders,
        "total_items": item_count,
        "total_amount": total_amount,
        "total_quantity": total_quantity,
        "by_supplier": by_supplier,
    }


# ---------------------------------------------------------------------------
# 接口 4：销售金额统计
# ---------------------------------------------------------------------------


def get_sales_summary(
    db: Session,
    start_date: date,
    end_date: date,
    customer_id: int | None = None,
) -> dict:
    """销售金额统计：指定日期范围内的订单数、明细数、总金额、总数量、按客户分组。"""
    order_filter = [
        SalesOrder.is_deleted == 0,
        func.date(SalesOrder.created_at) >= start_date,
        func.date(SalesOrder.created_at) <= end_date,
    ]
    if customer_id is not None:
        order_filter.append(SalesOrder.customer_id == customer_id)

    order_agg = db.execute(
        select(
            func.count(SalesOrder.id),
            func.coalesce(func.sum(SalesOrder.total_amount), 0),
            func.coalesce(func.sum(SalesOrder.total_quantity), 0),
        ).where(*order_filter)
    ).one()
    total_orders = order_agg[0] or 0
    total_amount = order_agg[1] or Decimal("0")
    total_quantity = order_agg[2] or Decimal("0")

    item_count = db.execute(
        select(func.count(SalesOrderItem.id))
        .join(SalesOrder, SalesOrderItem.sales_order_id == SalesOrder.id)
        .where(*order_filter)
    ).scalar() or 0

    by_customer_stmt = (
        select(
            SalesOrder.customer_id,
            Customer.name,
            func.count(SalesOrder.id),
            func.coalesce(func.sum(SalesOrder.total_amount), 0),
        )
        .join(Customer, SalesOrder.customer_id == Customer.id)
        .where(*order_filter)
        .group_by(SalesOrder.customer_id, Customer.name)
    )
    by_customer_rows = db.execute(by_customer_stmt).all()
    by_customer = [
        {
            "customer_id": row[0],
            "customer_name": row[1] or "",
            "order_count": row[2],
            "total_amount": row[3] or Decimal("0"),
        }
        for row in by_customer_rows
    ]

    return {
        "total_orders": total_orders,
        "total_items": item_count,
        "total_amount": total_amount,
        "total_quantity": total_quantity,
        "by_customer": by_customer,
    }
