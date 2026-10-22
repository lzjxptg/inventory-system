"""销售 CRUD。

提供销售订单与销售出库单的数据访问与业务逻辑：
- 订单 CRUD + 状态流转（submit / approve / cancel）
- 出库单创建 + 确认出库（联动库存）+ 取消
- 订单号 / 出库单号自动生成（SO-YYYYMMDD-序号 / SOUT-YYYYMMDD-序号）
- 金额计算：明细 amount = quantity * unit_price，头 total 由明细汇总

所有业务异常使用 core.exceptions 体系，不使用 HTTPException。
库存联动通过 crud.inventory.create_stock_movements 批量出库（quantity 传负数），
由本模块统一 commit。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from core.exceptions import ConflictException, NotFoundException, ValidationException
from crud.inventory import create_stock_movements
from models.customer import Customer
from models.customer_shop import CustomerShop
from models.product import Product
from models.sales import (
    SalesOrder,
    SalesOrderItem,
    SalesOut,
    SalesOutItem,
)
from models.warehouse import Warehouse
from schemas.inventory import StockMovementCreate
from schemas.sales import (
    SalesOutCreate,
    SalesOutItemCreate,
    SalesOrderCreate,
    SalesOrderUpdate,
)

# 订单状态常量
ORDER_STATUS_DRAFT = "draft"
ORDER_STATUS_SUBMITTED = "submitted"
ORDER_STATUS_APPROVED = "approved"
ORDER_STATUS_PARTIAL_OUT = "partial_out"
ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_CANCELLED = "cancelled"

# 出库单状态常量
OUT_STATUS_DRAFT = "draft"
OUT_STATUS_CONFIRMED = "confirmed"
OUT_STATUS_CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _generate_no(db: Session, prefix: str, model, column: str) -> str:
    """生成单据号：前缀-YYYYMMDD-序号（4位补零）。

    查询当天最大序号 +1；并发极小概率重复由唯一约束兜底，调用方捕获重试。
    """
    today = datetime.now().strftime("%Y%m%d")
    pattern = f"{prefix}-{today}-%"

    rows = db.execute(
        select(getattr(model, column)).where(getattr(model, column).like(pattern))
    ).scalars().all()

    max_seq = 0
    for no in rows:
        try:
            seq = int(no.split("-")[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    seq = max_seq + 1
    return f"{prefix}-{today}-{seq:04d}"


def _check_customer_warehouse(db: Session, customer_id: int, warehouse_id: int) -> None:
    """校验客户与仓库存在且未逻辑删除。"""
    customer = db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.is_deleted == 0)
    ).scalar_one_or_none()
    if customer is None:
        raise ValidationException("客户不存在或已删除")

    warehouse = db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.is_deleted == 0)
    ).scalar_one_or_none()
    if warehouse is None:
        raise ValidationException("仓库不存在或已删除")


def _check_product_exists(db: Session, product_id: int) -> None:
    """校验商品存在且未逻辑删除。"""
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.is_deleted == 0)
    ).scalar_one_or_none()
    if product is None:
        raise ValidationException(f"商品ID={product_id} 不存在或已删除")


def _check_shop_belongs_to_customer(
    db: Session, shop_id: int | None, customer_id: int
) -> None:
    """若指定了门店，校验该门店属于所选客户且未删除。"""
    if shop_id is None:
        return
    shop = db.execute(
        select(CustomerShop).where(
            CustomerShop.id == shop_id,
            CustomerShop.customer_id == customer_id,
            CustomerShop.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if shop is None:
        raise ValidationException("收货门店不存在或不属于该客户")


def _calc_order_totals(items: list) -> tuple[Decimal, Decimal]:
    """根据明细计算总数量与总金额。"""
    total_qty = Decimal("0")
    total_amt = Decimal("0")
    for item in items:
        qty = Decimal(str(item.quantity))
        price = Decimal(str(item.unit_price))
        total_qty += qty
        total_amt += qty * price
    return total_qty, total_amt


def _calc_out_totals(items: list[SalesOutItemCreate], order_items_map: dict) -> tuple[Decimal, Decimal]:
    """根据出库明细计算总数量与总金额。"""
    total_qty = Decimal("0")
    total_amt = Decimal("0")
    for item in items:
        qty = Decimal(str(item.quantity))
        price = item.unit_price if item.unit_price is not None else order_items_map[item.sales_order_item_id].unit_price
        total_qty += qty
        total_amt += qty * Decimal(str(price))
    return total_qty, total_amt


# ---------------------------------------------------------------------------
# 销售订单 CRUD
# ---------------------------------------------------------------------------


def get_order(db: Session, order_id: int) -> SalesOrder | None:
    """根据 ID 查询单个未删除订单（含明细）。"""
    stmt = (
        select(SalesOrder)
        .options(
            selectinload(SalesOrder.items),
            joinedload(SalesOrder.customer),
            joinedload(SalesOrder.warehouse),
            joinedload(SalesOrder.shop),
            joinedload(SalesOrder.creator),
            joinedload(SalesOrder.approver),
        )
        .where(SalesOrder.id == order_id, SalesOrder.is_deleted == 0)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_orders(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    customer_id: int | None = None,
    keyword: str | None = None,
) -> list[SalesOrder]:
    """分页查询未删除订单列表（含明细），支持按状态/客户/关键字筛选。"""
    stmt = (
        select(SalesOrder)
        .options(
            selectinload(SalesOrder.items),
            joinedload(SalesOrder.customer),
            joinedload(SalesOrder.warehouse),
            joinedload(SalesOrder.shop),
            joinedload(SalesOrder.creator),
            joinedload(SalesOrder.approver),
        )
        .where(SalesOrder.is_deleted == 0)
    )
    if status is not None:
        stmt = stmt.where(SalesOrder.status == status)
    if customer_id is not None:
        stmt = stmt.where(SalesOrder.customer_id == customer_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(SalesOrder.order_no.like(like), SalesOrder.remark.like(like))
        )
    stmt = stmt.order_by(SalesOrder.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().unique().all()


def create_order(db: Session, order_in: SalesOrderCreate, created_by: int) -> SalesOrder:
    """创建销售订单。

    - 校验客户、仓库、商品存在。
    - 校验同一订单内商品不重复。
    - 明细 amount、头 total 由 server 计算。
    - 状态默认 draft。
    """
    _check_customer_warehouse(db, order_in.customer_id, order_in.warehouse_id)
    _check_shop_belongs_to_customer(db, order_in.shop_id, order_in.customer_id)

    product_ids = [item.product_id for item in order_in.items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一订单内商品不能重复")
    for pid in product_ids:
        _check_product_exists(db, pid)

    total_qty, total_amt = _calc_order_totals(order_in.items)

    order_no = _generate_no(db, "SO", SalesOrder, "order_no")

    order = SalesOrder(
        order_no=order_no,
        customer_id=order_in.customer_id,
        warehouse_id=order_in.warehouse_id,
        shop_id=order_in.shop_id,
        status=ORDER_STATUS_DRAFT,
        total_quantity=total_qty,
        total_amount=total_amt,
        remark=order_in.remark,
        created_by=created_by,
    )
    db.add(order)
    db.flush()

    for item in order_in.items:
        qty = Decimal(str(item.quantity))
        price = Decimal(str(item.unit_price))
        db_item = SalesOrderItem(
            sales_order_id=order.id,
            product_id=item.product_id,
            quantity=qty,
            unit_price=price,
            amount=qty * price,
            shipped_quantity=Decimal("0"),
            remark=item.remark,
        )
        db.add(db_item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        order_no = _generate_no(db, "SO", SalesOrder, "order_no")
        order.order_no = order_no
        db.add(order)
        for item in order_in.items:
            qty = Decimal(str(item.quantity))
            price = Decimal(str(item.unit_price))
            db.add(
                SalesOrderItem(
                    sales_order_id=order.id,
                    product_id=item.product_id,
                    quantity=qty,
                    unit_price=price,
                    amount=qty * price,
                    shipped_quantity=Decimal("0"),
                    remark=item.remark,
                )
            )
        db.commit()

    db.refresh(order)
    return get_order(db, order.id)


def update_order(db: Session, order_id: int, order_in: SalesOrderUpdate) -> SalesOrder | None:
    """修改销售订单（仅 draft 可改，明细全量替换）。"""
    order = get_order(db, order_id)
    if order is None:
        return None
    if order.status != ORDER_STATUS_DRAFT:
        raise ConflictException(f"订单状态为 {order.status}，仅草稿可修改")

    _check_customer_warehouse(db, order_in.customer_id, order_in.warehouse_id)
    _check_shop_belongs_to_customer(db, order_in.shop_id, order_in.customer_id)

    product_ids = [item.product_id for item in order_in.items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一订单内商品不能重复")
    for pid in product_ids:
        _check_product_exists(db, pid)

    total_qty, total_amt = _calc_order_totals(order_in.items)

    order.customer_id = order_in.customer_id
    order.warehouse_id = order_in.warehouse_id
    order.shop_id = order_in.shop_id
    order.remark = order_in.remark
    order.total_quantity = total_qty
    order.total_amount = total_amt

    # 全量替换明细
    for old in order.items:
        db.delete(old)
    db.flush()

    for item in order_in.items:
        qty = Decimal(str(item.quantity))
        price = Decimal(str(item.unit_price))
        db.add(
            SalesOrderItem(
                sales_order_id=order.id,
                product_id=item.product_id,
                quantity=qty,
                unit_price=price,
                amount=qty * price,
                shipped_quantity=Decimal("0"),
                remark=item.remark,
            )
        )

    db.commit()
    return get_order(db, order.id)


def delete_order(db: Session, order_id: int) -> bool:
    """逻辑删除销售订单（仅 draft 可删）。"""
    order = get_order(db, order_id)
    if order is None:
        return False
    if order.status != ORDER_STATUS_DRAFT:
        raise ConflictException(f"订单状态为 {order.status}，仅草稿可删除")
    order.is_deleted = 1
    db.commit()
    return True


# ---------------------------------------------------------------------------
# 销售订单状态流转
# ---------------------------------------------------------------------------


def submit_order(db: Session, order_id: int) -> SalesOrder | None:
    """提交审核：draft -> submitted。"""
    order = get_order(db, order_id)
    if order is None:
        return None
    if order.status != ORDER_STATUS_DRAFT:
        raise ConflictException(f"订单状态为 {order.status}，仅草稿可提交审核")
    order.status = ORDER_STATUS_SUBMITTED
    db.commit()
    return get_order(db, order.id)


def approve_order(db: Session, order_id: int, approved_by: int) -> SalesOrder | None:
    """审核通过：submitted -> approved。"""
    order = get_order(db, order_id)
    if order is None:
        return None
    if order.status != ORDER_STATUS_SUBMITTED:
        raise ConflictException(f"订单状态为 {order.status}，仅待审核可审核通过")
    order.status = ORDER_STATUS_APPROVED
    order.approved_by = approved_by
    db.commit()
    return get_order(db, order.id)


def cancel_order(db: Session, order_id: int) -> SalesOrder | None:
    """取消订单：任意非 completed 态可取消。

    已出库（存在 confirmed 出库单）的订单不允许取消。
    取消订单时，将关联的 draft 出库单也标记为 cancelled。
    """
    order = get_order(db, order_id)
    if order is None:
        return None
    if order.status == ORDER_STATUS_COMPLETED:
        raise ConflictException("已完成订单不可取消")
    if order.status == ORDER_STATUS_CANCELLED:
        raise ConflictException("订单已取消，不可重复取消")

    # 已出库则不允许取消
    confirmed_out = db.execute(
        select(SalesOut.id).where(
            SalesOut.sales_order_id == order_id,
            SalesOut.status == OUT_STATUS_CONFIRMED,
            SalesOut.is_deleted == 0,
        ).limit(1)
    ).first()
    if confirmed_out is not None:
        raise ConflictException("订单已执行出库，不可取消")

    order.status = ORDER_STATUS_CANCELLED
    draft_outs = db.execute(
        select(SalesOut).where(
            SalesOut.sales_order_id == order_id,
            SalesOut.status == OUT_STATUS_DRAFT,
            SalesOut.is_deleted == 0,
        )
    ).scalars().all()
    for so in draft_outs:
        so.status = OUT_STATUS_CANCELLED
    db.commit()
    return get_order(db, order.id)


# ---------------------------------------------------------------------------
# 销售出库单
# ---------------------------------------------------------------------------


def get_out(db: Session, out_id: int) -> SalesOut | None:
    """根据 ID 查询单个未删除出库单（含明细）。"""
    stmt = (
        select(SalesOut)
        .options(
            selectinload(SalesOut.items),
            joinedload(SalesOut.customer),
            joinedload(SalesOut.warehouse),
            joinedload(SalesOut.order),
        )
        .where(SalesOut.id == out_id, SalesOut.is_deleted == 0)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_outs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    sales_order_id: int | None = None,
) -> list[SalesOut]:
    """分页查询未删除出库单列表（含明细），支持按状态/订单筛选。"""
    stmt = (
        select(SalesOut)
        .options(
            selectinload(SalesOut.items),
            joinedload(SalesOut.customer),
            joinedload(SalesOut.warehouse),
            joinedload(SalesOut.order),
        )
        .where(SalesOut.is_deleted == 0)
    )
    if status is not None:
        stmt = stmt.where(SalesOut.status == status)
    if sales_order_id is not None:
        stmt = stmt.where(SalesOut.sales_order_id == sales_order_id)
    stmt = stmt.order_by(SalesOut.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().unique().all()


def create_out_from_order(
    db: Session, order_id: int, out_data: SalesOutCreate, created_by: int
) -> SalesOut:
    """基于销售订单创建出库单（草稿）。

    - 校验订单状态为 approved 或 partial_out。
    - 校验明细 sales_order_item_id 属于该订单。
    - 校验本次出库数量 > 0 且不超过未出库数量（超发拦截）。
    - unit_price 不传则取订单明细单价。
    """
    order = get_order(db, order_id)
    if order is None:
        raise NotFoundException("销售订单不存在")
    if order.status not in (ORDER_STATUS_APPROVED, ORDER_STATUS_PARTIAL_OUT):
        raise ConflictException(f"订单状态为 {order.status}，仅已审核或部分出库可创建出库单")

    order_items_map = {item.id: item for item in order.items}

    product_ids = []
    for item in out_data.items:
        if item.sales_order_item_id not in order_items_map:
            raise ValidationException(
                f"订单明细ID={item.sales_order_item_id} 不属于该订单"
            )
        order_item = order_items_map[item.sales_order_item_id]
        remaining = order_item.quantity - order_item.shipped_quantity
        if item.quantity > remaining:
            raise ValidationException(
                f"商品ID={order_item.product_id} 出库数量超过未出库数量"
                f"（本次={item.quantity}，剩余={remaining}）"
            )
        product_ids.append(order_item.product_id)

    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一出库单内商品不能重复")

    total_qty, total_amt = _calc_out_totals(out_data.items, order_items_map)

    out_no = _generate_no(db, "SOUT", SalesOut, "out_no")

    sales_out = SalesOut(
        out_no=out_no,
        sales_order_id=order_id,
        customer_id=order.customer_id,
        warehouse_id=order.warehouse_id,
        status=OUT_STATUS_DRAFT,
        total_quantity=total_qty,
        total_amount=total_amt,
        created_by=created_by,
    )
    db.add(sales_out)
    db.flush()

    for item in out_data.items:
        order_item = order_items_map[item.sales_order_item_id]
        qty = Decimal(str(item.quantity))
        price = (
            Decimal(str(item.unit_price))
            if item.unit_price is not None
            else order_item.unit_price
        )
        db.add(
            SalesOutItem(
                sales_out_id=sales_out.id,
                sales_order_item_id=item.sales_order_item_id,
                product_id=order_item.product_id,
                quantity=qty,
                unit_price=price,
                amount=qty * price,
                batch_no=item.batch_no,
                remark=item.remark,
            )
        )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        out_no = _generate_no(db, "SOUT", SalesOut, "out_no")
        sales_out.out_no = out_no
        db.add(sales_out)
        for item in out_data.items:
            order_item = order_items_map[item.sales_order_item_id]
            qty = Decimal(str(item.quantity))
            price = (
                Decimal(str(item.unit_price))
                if item.unit_price is not None
                else order_item.unit_price
            )
            db.add(
                SalesOutItem(
                    sales_out_id=sales_out.id,
                    sales_order_item_id=item.sales_order_item_id,
                    product_id=order_item.product_id,
                    quantity=qty,
                    unit_price=price,
                    amount=qty * price,
                    batch_no=item.batch_no,
                    remark=item.remark,
                )
            )
        db.commit()

    return get_out(db, sales_out.id)


def confirm_out(db: Session, out_id: int, operator_id: int) -> SalesOut | None:
    """确认出库（核心接口，联动库存减少）。

    同一事务内：
    1. 校验出库单状态为 draft。
    2. 逐条校验超发（shipped_quantity + 本次 <= quantity）。
    3. 累加 sales_order_items.shipped_quantity。
    4. 更新出库单状态为 confirmed，记录确认人和时间。
    5. 更新订单状态（partial_out / completed）。
    6. 调用 create_stock_movements 批量出库（quantity 传负数，只 flush）。
    7. db.commit() 一次提交。
    """
    sales_out = get_out(db, out_id)
    if sales_out is None:
        return None
    if sales_out.status != OUT_STATUS_DRAFT:
        raise ConflictException(f"出库单状态为 {sales_out.status}，仅草稿可确认")

    order = get_order(db, sales_out.sales_order_id)
    if order is None:
        raise NotFoundException("关联销售订单不存在")

    order_items_map = {item.id: item for item in order.items}

    # 逐条校验超发 + 累加 shipped_quantity + 构造出库流水
    movements: list[StockMovementCreate] = []
    for out_item in sales_out.items:
        order_item = order_items_map.get(out_item.sales_order_item_id)
        if order_item is None:
            raise ValidationException(f"订单明细ID={out_item.sales_order_item_id} 不存在")

        new_shipped = order_item.shipped_quantity + out_item.quantity
        if new_shipped > order_item.quantity:
            raise ValidationException(
                f"商品ID={out_item.product_id} 出库数量超过订购数量"
                f"（已发={order_item.shipped_quantity}，本次={out_item.quantity}，订购={order_item.quantity}）"
            )
        order_item.shipped_quantity = new_shipped

        # 构造库存流水（出库 quantity 为负，schema 按 movement_type 校验符号）
        movements.append(
            StockMovementCreate(
                product_id=out_item.product_id,
                warehouse_id=sales_out.warehouse_id,
                movement_type="OUT",
                quantity=-out_item.quantity,
                reference_type="SALE",
                reference_id=sales_out.id,
                remark=out_item.batch_no,
            )
        )

    # 更新出库单状态
    sales_out.status = OUT_STATUS_CONFIRMED
    sales_out.confirmed_by = operator_id
    sales_out.confirmed_at = func.now()

    # 更新订单状态：全部明细发齐 -> completed，否则 -> partial_out
    all_shipped = all(
        item.shipped_quantity >= item.quantity for item in order.items
    )
    order.status = ORDER_STATUS_COMPLETED if all_shipped else ORDER_STATUS_PARTIAL_OUT

    # 批量出库（只 flush，不 commit；超卖拦截由内部完成，库存不足抛 ValidationException）
    # 任一环节异常（含库存不足）都回滚整个事务，保证订单/出库单/库存原子一致。
    try:
        create_stock_movements(db, movements, operator_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_out(db, out_id)


def cancel_out(db: Session, out_id: int) -> SalesOut | None:
    """取消出库单（仅 draft 可取消）。"""
    sales_out = get_out(db, out_id)
    if sales_out is None:
        return None
    if sales_out.status == OUT_STATUS_CONFIRMED:
        raise ConflictException("已确认出库单不可取消")
    if sales_out.status == OUT_STATUS_CANCELLED:
        raise ConflictException("出库单已取消，不可重复取消")
    sales_out.status = OUT_STATUS_CANCELLED
    db.commit()
    return get_out(db, out_id)
