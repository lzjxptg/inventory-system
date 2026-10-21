"""采购退货 CRUD。

提供采购退货单的数据访问与业务逻辑：
- 创建 / 列表 / 详情 / 修改 / 删除
- 状态流转：submit（提交） / approve（审核通过，联动库存入库） / reject（驳回）
- 退货单号自动生成（PR-YYYYMMDD-序号）
- 退货数量不得超过原订单已入库数量
- 审核通过时，商品退回仓库 → inventory_balance 增加 + stock_movements 写入 IN 流水

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
from crud.purchase import get_order as get_purchase_order
from models.product import Product
from models.purchase import PurchaseOrderItem
from models.purchase_return import PurchaseReturn, PurchaseReturnItem
from models.supplier import Supplier
from models.warehouse import Warehouse
from schemas.inventory import StockMovementCreate
from schemas.purchase_return import PurchaseReturnCreate, PurchaseReturnUpdate

# 退货单状态常量
RETURN_STATUS_DRAFT = "draft"
RETURN_STATUS_SUBMITTED = "submitted"
RETURN_STATUS_APPROVED = "approved"
RETURN_STATUS_REJECTED = "rejected"

# 允许创建退货单的采购订单状态
ALLOWED_ORDER_STATUSES = ("approved", "partial_in", "received", "completed")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _generate_no(db: Session) -> str:
    """生成退货单号：PR-YYYYMMDD-序号（4位补零）。"""
    today = datetime.now().strftime("%Y%m%d")
    pattern = f"PR-{today}-%"
    rows = db.execute(
        select(PurchaseReturn.return_no).where(PurchaseReturn.return_no.like(pattern))
    ).scalars().all()

    max_seq = 0
    for no in rows:
        try:
            seq = int(no.split("-")[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue
    return f"PR-{today}-{max_seq + 1:04d}"


def _calc_totals(items: list) -> tuple[Decimal, Decimal]:
    """根据明细计算总数量与总金额。"""
    total_qty = Decimal("0")
    total_amt = Decimal("0")
    for item in items:
        qty = Decimal(str(item.quantity))
        price = Decimal(str(item.unit_price))
        total_qty += qty
        total_amt += qty * price
    return total_qty, total_amt


def _get_order_item_by_product(
    order_items: list[PurchaseOrderItem], product_id: int
) -> PurchaseOrderItem | None:
    """在订单明细中按 product_id 查找。"""
    for it in order_items:
        if it.product_id == product_id:
            return it
    return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def get_return(db: Session, return_id: int) -> PurchaseReturn | None:
    """根据 ID 查询单个未删除退货单（含明细）。"""
    stmt = (
        select(PurchaseReturn)
        .options(
            selectinload(PurchaseReturn.items),
            joinedload(PurchaseReturn.supplier),
            joinedload(PurchaseReturn.warehouse),
            joinedload(PurchaseReturn.order),
        )
        .where(PurchaseReturn.id == return_id, PurchaseReturn.is_deleted == 0)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_returns(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    supplier_id: int | None = None,
    keyword: str | None = None,
) -> list[PurchaseReturn]:
    """分页查询未删除退货单列表（含明细）。"""
    stmt = (
        select(PurchaseReturn)
        .options(
            selectinload(PurchaseReturn.items),
            joinedload(PurchaseReturn.supplier),
            joinedload(PurchaseReturn.warehouse),
            joinedload(PurchaseReturn.order),
        )
        .where(PurchaseReturn.is_deleted == 0)
    )
    if status is not None:
        stmt = stmt.where(PurchaseReturn.status == status)
    if supplier_id is not None:
        stmt = stmt.where(PurchaseReturn.supplier_id == supplier_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(PurchaseReturn.return_no.like(like), PurchaseReturn.reason.like(like))
        )
    stmt = stmt.order_by(PurchaseReturn.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().unique().all()


def get_returns_by_order_id(db: Session, order_id: int) -> list[PurchaseReturn]:
    """查询某采购订单下所有未删除退货单。"""
    stmt = (
        select(PurchaseReturn)
        .options(selectinload(PurchaseReturn.items))
        .where(
            PurchaseReturn.purchase_order_id == order_id,
            PurchaseReturn.is_deleted == 0,
        )
    )
    return db.execute(stmt).scalars().all()


def create_return(
    db: Session, ret_in: PurchaseReturnCreate, created_by: int
) -> PurchaseReturn:
    """创建采购退货单（草稿）。

    - 校验采购订单存在且状态允许退货。
    - 校验退货商品属于该订单，退货数量不超过已入库数量。
    - unit_price 不传则取订单明细单价。
    """
    order = get_purchase_order(db, ret_in.purchase_order_id)
    if order is None:
        raise NotFoundException("采购订单不存在")
    if order.status not in ALLOWED_ORDER_STATUSES:
        raise ConflictException(
            f"采购订单状态为 {order.status}，仅已审核/部分入库/已收货/已完成订单可退货"
        )

    # 校验供应商/仓库存在
    supplier = db.execute(
        select(Supplier).where(Supplier.id == order.supplier_id, Supplier.is_deleted == 0)
    ).scalar_one_or_none()
    if supplier is None:
        raise ValidationException("供应商不存在或已删除")
    warehouse = db.execute(
        select(Warehouse).where(Warehouse.id == order.warehouse_id, Warehouse.is_deleted == 0)
    ).scalar_one_or_none()
    if warehouse is None:
        raise ValidationException("仓库不存在或已删除")

    order_items_map = {item.product_id: item for item in order.items}

    product_ids = []
    for item in ret_in.items:
        order_item = order_items_map.get(item.product_id)
        if order_item is None:
            raise ValidationException(f"商品ID={item.product_id} 不在该采购订单中")
        if item.quantity > order_item.received_quantity:
            raise ValidationException(
                f"商品ID={item.product_id} 退货数量超过已入库数量"
                f"（退货={item.quantity}，已入库={order_item.received_quantity}）"
            )
        product_ids.append(item.product_id)

    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一退货单内商品不能重复")

    return_no = _generate_no(db)

    total_qty = Decimal("0")
    total_amt = Decimal("0")
    db_items: list[PurchaseReturnItem] = []
    for item in ret_in.items:
        order_item = order_items_map[item.product_id]
        qty = Decimal(str(item.quantity))
        price = (
            Decimal(str(item.unit_price))
            if item.unit_price is not None
            else order_item.unit_price
        )
        total_qty += qty
        total_amt += qty * price
        db_items.append(
            PurchaseReturnItem(
                product_id=item.product_id,
                quantity=qty,
                unit_price=price,
                amount=qty * price,
                batch_no=item.batch_no,
            )
        )

    ret = PurchaseReturn(
        return_no=return_no,
        purchase_order_id=order.id,
        supplier_id=order.supplier_id,
        warehouse_id=order.warehouse_id,
        total_quantity=total_qty,
        total_amount=total_amt,
        status=RETURN_STATUS_DRAFT,
        reason=ret_in.reason,
        created_by=created_by,
    )
    ret.items = db_items
    db.add(ret)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        ret.return_no = _generate_no(db)
        db.add(ret)
        db.commit()

    db.refresh(ret)
    return get_return(db, ret.id)


def update_return(
    db: Session, return_id: int, ret_in: PurchaseReturnUpdate
) -> PurchaseReturn | None:
    """修改采购退货单（仅 draft 可改，明细全量替换）。"""
    ret = get_return(db, return_id)
    if ret is None:
        return None
    if ret.status != RETURN_STATUS_DRAFT:
        raise ConflictException(f"退货单状态为 {ret.status}，仅草稿可修改")

    order = get_purchase_order(db, ret.purchase_order_id)
    if order is None:
        raise NotFoundException("采购订单不存在")
    order_items_map = {item.product_id: item for item in order.items}

    product_ids = []
    for item in ret_in.items:
        order_item = order_items_map.get(item.product_id)
        if order_item is None:
            raise ValidationException(f"商品ID={item.product_id} 不在该采购订单中")
        if item.quantity > order_item.received_quantity:
            raise ValidationException(
                f"商品ID={item.product_id} 退货数量超过已入库数量"
            )
        product_ids.append(item.product_id)
    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一退货单内商品不能重复")

    total_qty = Decimal("0")
    total_amt = Decimal("0")
    for item in ret_in.items:
        order_item = order_items_map[item.product_id]
        qty = Decimal(str(item.quantity))
        price = (
            Decimal(str(item.unit_price))
            if item.unit_price is not None
            else order_item.unit_price
        )
        total_qty += qty
        total_amt += qty * price

    ret.reason = ret_in.reason
    ret.total_quantity = total_qty
    ret.total_amount = total_amt

    for old in ret.items:
        db.delete(old)
    db.flush()

    for item in ret_in.items:
        order_item = order_items_map[item.product_id]
        qty = Decimal(str(item.quantity))
        price = (
            Decimal(str(item.unit_price))
            if item.unit_price is not None
            else order_item.unit_price
        )
        db.add(
            PurchaseReturnItem(
                return_id=ret.id,
                product_id=item.product_id,
                quantity=qty,
                unit_price=price,
                amount=qty * price,
                batch_no=item.batch_no,
            )
        )

    db.commit()
    return get_return(db, ret.id)


def delete_return(db: Session, return_id: int) -> bool:
    """逻辑删除采购退货单（仅 draft 可删）。"""
    ret = get_return(db, return_id)
    if ret is None:
        return False
    if ret.status != RETURN_STATUS_DRAFT:
        raise ConflictException(f"退货单状态为 {ret.status}，仅草稿可删除")
    ret.is_deleted = 1
    db.commit()
    return True


# ---------------------------------------------------------------------------
# 状态流转
# ---------------------------------------------------------------------------


def submit_return(db: Session, return_id: int) -> PurchaseReturn | None:
    """提交审核：draft -> submitted。"""
    ret = get_return(db, return_id)
    if ret is None:
        return None
    if ret.status != RETURN_STATUS_DRAFT:
        raise ConflictException(f"退货单状态为 {ret.status}，仅草稿可提交审核")
    ret.status = RETURN_STATUS_SUBMITTED
    db.commit()
    return get_return(db, ret.id)


def approve_return(db: Session, return_id: int, approved_by: int) -> PurchaseReturn | None:
    """审核通过：submitted -> approved，联动库存（商品退回仓库，IN 流水）。

    同一事务内：
    1. 校验状态为 submitted。
    2. 逐条构造 IN 流水（quantity 为正）。
    3. 调用 create_stock_movements 批量入库（只 flush）。
    4. 更新状态为 approved，记录审核人和时间。
    5. db.commit() 统一提交。
    """
    ret = get_return(db, return_id)
    if ret is None:
        return None
    if ret.status != RETURN_STATUS_SUBMITTED:
        raise ConflictException(f"退货单状态为 {ret.status}，仅待审核可审核通过")

    movements: list[StockMovementCreate] = []
    for item in ret.items:
        movements.append(
            StockMovementCreate(
                product_id=item.product_id,
                warehouse_id=ret.warehouse_id,
                movement_type="IN",
                quantity=item.quantity,
                reference_type="PURCHASE_RETURN",
                reference_id=ret.id,
                remark=item.batch_no,
            )
        )

    create_stock_movements(db, movements, approved_by)

    ret.status = RETURN_STATUS_APPROVED
    ret.approved_by = approved_by
    ret.approved_at = func.now()
    db.commit()
    return get_return(db, ret.id)


def reject_return(db: Session, return_id: int) -> PurchaseReturn | None:
    """驳回：submitted -> rejected。"""
    ret = get_return(db, return_id)
    if ret is None:
        return None
    if ret.status != RETURN_STATUS_SUBMITTED:
        raise ConflictException(f"退货单状态为 {ret.status}，仅待审核可驳回")
    ret.status = RETURN_STATUS_REJECTED
    db.commit()
    return get_return(db, ret.id)
