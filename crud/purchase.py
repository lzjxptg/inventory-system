"""采购 CRUD。

提供采购订单与采购入库单的数据访问与业务逻辑：
- 订单 CRUD + 状态流转（submit / approve / cancel）
- 入库单创建 + 确认入库（联动库存）+ 取消
- 订单号 / 入库单号自动生成（PO-YYYYMMDD-序号 / PI-YYYYMMDD-序号）
- 金额计算：明细 amount = quantity * unit_price，头 total 由明细汇总

所有业务异常使用 core.exceptions 体系，不使用 HTTPException。
库存联动通过 crud.inventory.create_stock_movements 批量入库，由本模块统一 commit。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from core.exceptions import ConflictException, NotFoundException, ValidationException
from crud.inventory import create_stock_movements
from models.purchase import (
    PurchaseIn,
    PurchaseInItem,
    PurchaseOrder,
    PurchaseOrderItem,
)
from models.product import Product
from models.supplier import Supplier
from models.warehouse import Warehouse
from schemas.inventory import StockMovementCreate
from schemas.purchase import (
    PurchaseInCreate,
    PurchaseInItemCreate,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
)

# 订单状态常量
ORDER_STATUS_DRAFT = "draft"
ORDER_STATUS_SUBMITTED = "submitted"
ORDER_STATUS_APPROVED = "approved"
ORDER_STATUS_PARTIAL_IN = "partial_in"
ORDER_STATUS_RECEIVED = "received"
ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_CANCELLED = "cancelled"

# 入库单状态常量
IN_STATUS_DRAFT = "draft"
IN_STATUS_CONFIRMED = "confirmed"
IN_STATUS_CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _generate_no(db: Session, prefix: str, model, column: str) -> str:
    """生成单据号：前缀-YYYYMMDD-序号（4位补零）。

    查询当天最大序号 +1；并发极小概率重复由唯一约束兜底，调用方捕获重试。
    """
    today = datetime.now().strftime("%Y%m%d")
    pattern = f"{prefix}-{today}-%"

    # 取当天所有单据号，提取最大序号
    rows = db.execute(
        select(getattr(model, column)).where(getattr(model, column).like(pattern))
    ).scalars().all()

    max_seq = 0
    for no in rows:
        # 格式 PO-YYYYMMDD-1234，取最后一段
        try:
            seq = int(no.split("-")[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue

    seq = max_seq + 1
    return f"{prefix}-{today}-{seq:04d}"


def _check_supplier_warehouse(db: Session, supplier_id: int, warehouse_id: int) -> None:
    """校验供应商与仓库存在且未逻辑删除。"""
    supplier = db.execute(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.is_deleted == 0)
    ).scalar_one_or_none()
    if supplier is None:
        raise ValidationException("供应商不存在或已删除")

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


def _calc_in_totals(items: list[PurchaseInItemCreate], order_items_map: dict) -> tuple[Decimal, Decimal]:
    """根据入库明细计算总数量与总金额。"""
    total_qty = Decimal("0")
    total_amt = Decimal("0")
    for item in items:
        qty = Decimal(str(item.quantity))
        price = item.unit_price if item.unit_price is not None else order_items_map[item.purchase_order_item_id].unit_price
        total_qty += qty
        total_amt += qty * Decimal(str(price))
    return total_qty, total_amt


# ---------------------------------------------------------------------------
# 采购订单 CRUD
# ---------------------------------------------------------------------------


def get_order(db: Session, order_id: int) -> PurchaseOrder | None:
    """根据 ID 查询单个未删除订单（含明细）。"""
    stmt = (
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.items),
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.warehouse),
        )
        .where(PurchaseOrder.id == order_id, PurchaseOrder.is_deleted == 0)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_orders(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    supplier_id: int | None = None,
    keyword: str | None = None,
) -> list[PurchaseOrder]:
    """分页查询未删除订单列表（含明细），支持按状态/供应商/关键字筛选。"""
    stmt = (
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.items),
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.warehouse),
        )
        .where(PurchaseOrder.is_deleted == 0)
    )
    if status is not None:
        stmt = stmt.where(PurchaseOrder.status == status)
    if supplier_id is not None:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(PurchaseOrder.order_no.like(like), PurchaseOrder.remark.like(like))
        )
    stmt = stmt.order_by(PurchaseOrder.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().unique().all()


def create_order(db: Session, order_in: PurchaseOrderCreate, created_by: int) -> PurchaseOrder:
    """创建采购订单。

    - 校验供应商、仓库、商品存在。
    - 校验同一订单内商品不重复。
    - 明细 amount、头 total 由 server 计算。
    - 状态默认 draft。
    """
    _check_supplier_warehouse(db, order_in.supplier_id, order_in.warehouse_id)

    # 校验商品存在 + 同一订单内商品不重复
    product_ids = [item.product_id for item in order_in.items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一订单内商品不能重复")
    for pid in product_ids:
        _check_product_exists(db, pid)

    total_qty, total_amt = _calc_order_totals(order_in.items)

    # 生成订单号（唯一约束兜底重试一次）
    order_no = _generate_no(db, "PO", PurchaseOrder, "order_no")

    order = PurchaseOrder(
        order_no=order_no,
        supplier_id=order_in.supplier_id,
        warehouse_id=order_in.warehouse_id,
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
        db_item = PurchaseOrderItem(
            purchase_order_id=order.id,
            product_id=item.product_id,
            quantity=qty,
            unit_price=price,
            amount=qty * price,
            received_quantity=Decimal("0"),
            remark=item.remark,
        )
        db.add(db_item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 订单号重复，重试一次
        order_no = _generate_no(db, "PO", PurchaseOrder, "order_no")
        order.order_no = order_no
        db.add(order)
        for item in order_in.items:
            qty = Decimal(str(item.quantity))
            price = Decimal(str(item.unit_price))
            db.add(
                PurchaseOrderItem(
                    purchase_order_id=order.id,
                    product_id=item.product_id,
                    quantity=qty,
                    unit_price=price,
                    amount=qty * price,
                    received_quantity=Decimal("0"),
                    remark=item.remark,
                )
            )
        db.commit()

    db.refresh(order)
    return get_order(db, order.id)


def update_order(db: Session, order_id: int, order_in: PurchaseOrderUpdate) -> PurchaseOrder | None:
    """修改采购订单（仅 draft 可改，明细全量替换）。"""
    order = get_order(db, order_id)
    if order is None:
        return None
    if order.status != ORDER_STATUS_DRAFT:
        raise ConflictException(f"订单状态为 {order.status}，仅草稿可修改")

    _check_supplier_warehouse(db, order_in.supplier_id, order_in.warehouse_id)

    product_ids = [item.product_id for item in order_in.items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一订单内商品不能重复")
    for pid in product_ids:
        _check_product_exists(db, pid)

    total_qty, total_amt = _calc_order_totals(order_in.items)

    order.supplier_id = order_in.supplier_id
    order.warehouse_id = order_in.warehouse_id
    order.remark = order_in.remark
    order.total_quantity = total_qty
    order.total_amount = total_amt

    # 全量替换明细：删除旧明细，新增新明细
    for old in order.items:
        db.delete(old)
    db.flush()

    for item in order_in.items:
        qty = Decimal(str(item.quantity))
        price = Decimal(str(item.unit_price))
        db.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                product_id=item.product_id,
                quantity=qty,
                unit_price=price,
                amount=qty * price,
                received_quantity=Decimal("0"),
                remark=item.remark,
            )
        )

    db.commit()
    return get_order(db, order.id)


def delete_order(db: Session, order_id: int) -> bool:
    """逻辑删除采购订单（仅 draft 可删）。"""
    order = get_order(db, order_id)
    if order is None:
        return False
    if order.status != ORDER_STATUS_DRAFT:
        raise ConflictException(f"订单状态为 {order.status}，仅草稿可删除")
    order.is_deleted = 1
    db.commit()
    return True


# ---------------------------------------------------------------------------
# 采购订单状态流转
# ---------------------------------------------------------------------------


def submit_order(db: Session, order_id: int) -> PurchaseOrder | None:
    """提交审核：draft -> submitted。"""
    order = get_order(db, order_id)
    if order is None:
        return None
    if order.status != ORDER_STATUS_DRAFT:
        raise ConflictException(f"订单状态为 {order.status}，仅草稿可提交审核")
    order.status = ORDER_STATUS_SUBMITTED
    db.commit()
    return get_order(db, order.id)


def approve_order(db: Session, order_id: int, approved_by: int) -> PurchaseOrder | None:
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


def cancel_order(db: Session, order_id: int) -> PurchaseOrder | None:
    """取消订单：任意非 completed 态可取消。"""
    order = get_order(db, order_id)
    if order is None:
        return None
    if order.status == ORDER_STATUS_COMPLETED:
        raise ConflictException("已完成订单不可取消")
    if order.status == ORDER_STATUS_CANCELLED:
        raise ConflictException("订单已取消，不可重复取消")
    order.status = ORDER_STATUS_CANCELLED
    # 取消订单时，将关联的 draft 入库单也标记为 cancelled
    draft_ins = db.execute(
        select(PurchaseIn).where(
            PurchaseIn.purchase_order_id == order_id,
            PurchaseIn.status == IN_STATUS_DRAFT,
            PurchaseIn.is_deleted == 0,
        )
    ).scalars().all()
    for pi in draft_ins:
        pi.status = IN_STATUS_CANCELLED
    db.commit()
    return get_order(db, order.id)


# ---------------------------------------------------------------------------
# 采购入库单
# ---------------------------------------------------------------------------


def get_in(db: Session, in_id: int) -> PurchaseIn | None:
    """根据 ID 查询单个未删除入库单（含明细）。"""
    stmt = (
        select(PurchaseIn)
        .options(
            selectinload(PurchaseIn.items),
            joinedload(PurchaseIn.supplier),
            joinedload(PurchaseIn.warehouse),
            joinedload(PurchaseIn.order),
        )
        .where(PurchaseIn.id == in_id, PurchaseIn.is_deleted == 0)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_ins(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    purchase_order_id: int | None = None,
) -> list[PurchaseIn]:
    """分页查询未删除入库单列表（含明细），支持按状态/订单筛选。"""
    stmt = (
        select(PurchaseIn)
        .options(
            selectinload(PurchaseIn.items),
            joinedload(PurchaseIn.supplier),
            joinedload(PurchaseIn.warehouse),
            joinedload(PurchaseIn.order),
        )
        .where(PurchaseIn.is_deleted == 0)
    )
    if status is not None:
        stmt = stmt.where(PurchaseIn.status == status)
    if purchase_order_id is not None:
        stmt = stmt.where(PurchaseIn.purchase_order_id == purchase_order_id)
    stmt = stmt.order_by(PurchaseIn.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().unique().all()


def create_in_from_order(
    db: Session, order_id: int, in_data: PurchaseInCreate, created_by: int
) -> PurchaseIn:
    """基于采购订单创建入库单（草稿）。

    - 校验订单状态为 approved 或 partial_in。
    - 校验明细 purchase_order_item_id 属于该订单。
    - 校验本次入库数量 > 0 且不超过未入库数量。
    - unit_price 不传则取订单明细单价。
    """
    order = get_order(db, order_id)
    if order is None:
        raise NotFoundException("采购订单不存在")
    if order.status not in (ORDER_STATUS_APPROVED, ORDER_STATUS_PARTIAL_IN):
        raise ConflictException(f"订单状态为 {order.status}，仅已审核或部分入库可创建入库单")

    # 构建订单明细 map：id -> PurchaseOrderItem
    order_items_map = {item.id: item for item in order.items}

    # 校验明细
    product_ids = []
    for item in in_data.items:
        if item.purchase_order_item_id not in order_items_map:
            raise ValidationException(
                f"订单明细ID={item.purchase_order_item_id} 不属于该订单"
            )
        order_item = order_items_map[item.purchase_order_item_id]
        remaining = order_item.quantity - order_item.received_quantity
        if item.quantity > remaining:
            raise ValidationException(
                f"商品ID={order_item.product_id} 入库数量超过未入库数量"
                f"（本次={item.quantity}，剩余={remaining}）"
            )
        product_ids.append(order_item.product_id)

    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一入库单内商品不能重复")

    total_qty, total_amt = _calc_in_totals(in_data.items, order_items_map)

    in_no = _generate_no(db, "PI", PurchaseIn, "in_no")

    purchase_in = PurchaseIn(
        in_no=in_no,
        purchase_order_id=order_id,
        supplier_id=order.supplier_id,
        warehouse_id=order.warehouse_id,
        status=IN_STATUS_DRAFT,
        total_quantity=total_qty,
        total_amount=total_amt,
        created_by=created_by,
    )
    db.add(purchase_in)
    db.flush()

    for item in in_data.items:
        order_item = order_items_map[item.purchase_order_item_id]
        qty = Decimal(str(item.quantity))
        price = (
            Decimal(str(item.unit_price))
            if item.unit_price is not None
            else order_item.unit_price
        )
        db.add(
            PurchaseInItem(
                purchase_in_id=purchase_in.id,
                purchase_order_item_id=item.purchase_order_item_id,
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
        in_no = _generate_no(db, "PI", PurchaseIn, "in_no")
        purchase_in.in_no = in_no
        db.add(purchase_in)
        for item in in_data.items:
            order_item = order_items_map[item.purchase_order_item_id]
            qty = Decimal(str(item.quantity))
            price = (
                Decimal(str(item.unit_price))
                if item.unit_price is not None
                else order_item.unit_price
            )
            db.add(
                PurchaseInItem(
                    purchase_in_id=purchase_in.id,
                    purchase_order_item_id=item.purchase_order_item_id,
                    product_id=order_item.product_id,
                    quantity=qty,
                    unit_price=price,
                    amount=qty * price,
                    batch_no=item.batch_no,
                    remark=item.remark,
                )
            )
        db.commit()

    return get_in(db, purchase_in.id)


def confirm_in(db: Session, in_id: int, operator_id: int) -> PurchaseIn | None:
    """确认入库（核心接口，联动库存）。

    同一事务内：
    1. 校验入库单状态为 draft。
    2. 逐条校验超收（received_quantity + 本次 <= quantity）。
    3. 累加 purchase_order_items.received_quantity。
    4. 更新入库单状态为 confirmed，记录确认人和时间。
    5. 更新订单状态（partial_in / completed）。
    6. 调用 create_stock_movements 批量入库（只 flush）。
    7. db.commit() 一次提交。
    """
    purchase_in = get_in(db, in_id)
    if purchase_in is None:
        return None
    if purchase_in.status != IN_STATUS_DRAFT:
        raise ConflictException(f"入库单状态为 {purchase_in.status}，仅草稿可确认")

    order = get_order(db, purchase_in.purchase_order_id)
    if order is None:
        raise NotFoundException("关联采购订单不存在")

    # 构建订单明细 map
    order_items_map = {item.id: item for item in order.items}

    # 逐条校验超收 + 累加 received_quantity
    movements: list[StockMovementCreate] = []
    for in_item in purchase_in.items:
        order_item = order_items_map.get(in_item.purchase_order_item_id)
        if order_item is None:
            raise ValidationException(f"订单明细ID={in_item.purchase_order_item_id} 不存在")

        new_received = order_item.received_quantity + in_item.quantity
        if new_received > order_item.quantity:
            raise ValidationException(
                f"商品ID={in_item.product_id} 入库数量超过订购数量"
                f"（已入={order_item.received_quantity}，本次={in_item.quantity}，订购={order_item.quantity}）"
            )
        order_item.received_quantity = new_received

        # 构造库存流水（入库 quantity 为正）
        movements.append(
            StockMovementCreate(
                product_id=in_item.product_id,
                warehouse_id=purchase_in.warehouse_id,
                movement_type="IN",
                quantity=in_item.quantity,
                reference_type="PURCHASE",
                reference_id=purchase_in.id,
                remark=in_item.batch_no,
            )
        )

    # 更新入库单状态
    purchase_in.status = IN_STATUS_CONFIRMED
    purchase_in.confirmed_by = operator_id
    purchase_in.confirmed_at = func.now()

    # 更新订单状态：全部明细收齐 -> completed，否则 -> partial_in
    all_received = all(
        item.received_quantity >= item.quantity for item in order.items
    )
    order.status = ORDER_STATUS_COMPLETED if all_received else ORDER_STATUS_PARTIAL_IN

    # 批量入库（只 flush，不 commit）
    create_stock_movements(db, movements, operator_id)

    # 统一提交事务
    db.commit()
    return get_in(db, in_id)


def cancel_in(db: Session, in_id: int) -> PurchaseIn | None:
    """取消入库单（仅 draft 可取消）。"""
    purchase_in = get_in(db, in_id)
    if purchase_in is None:
        return None
    if purchase_in.status == IN_STATUS_CONFIRMED:
        raise ConflictException("已确认入库单不可取消")
    if purchase_in.status == IN_STATUS_CANCELLED:
        raise ConflictException("入库单已取消，不可重复取消")
    purchase_in.status = IN_STATUS_CANCELLED
    db.commit()
    return get_in(db, in_id)
