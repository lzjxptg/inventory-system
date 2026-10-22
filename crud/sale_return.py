"""销售退货 CRUD。

对称于采购退货：
- 创建 / 列表 / 详情 / 修改 / 删除
- 状态流转：submit / approve（审核通过，联动库存出库） / reject
- 退货单号自动生成（SR-YYYYMMDD-序号）
- 退货数量不得超过原订单已出库数量
- 审核通过时，商品从仓库出库（退回客户） → inventory_balance 扣减 + stock_movements 写入 OUT 流水
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from core.exceptions import ConflictException, NotFoundException, ValidationException
from crud.inventory import create_stock_movements
from crud.sales import get_order as get_sales_order
from models.customer import Customer
from models.sale_return import SalesReturn, SalesReturnItem
from models.sales import SalesOrderItem
from models.warehouse import Warehouse
from schemas.inventory import StockMovementCreate
from schemas.sale_return import SalesReturnCreate, SalesReturnUpdate

RETURN_STATUS_DRAFT = "draft"
RETURN_STATUS_SUBMITTED = "submitted"
RETURN_STATUS_APPROVED = "approved"
RETURN_STATUS_REJECTED = "rejected"

ALLOWED_ORDER_STATUSES = ("approved", "partial_out", "completed")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _generate_no(db: Session) -> str:
    """生成退货单号：SR-YYYYMMDD-序号（4位补零）。"""
    today = datetime.now().strftime("%Y%m%d")
    pattern = f"SR-{today}-%"
    rows = db.execute(
        select(SalesReturn.return_no).where(SalesReturn.return_no.like(pattern))
    ).scalars().all()

    max_seq = 0
    for no in rows:
        try:
            seq = int(no.split("-")[-1])
            if seq > max_seq:
                max_seq = seq
        except (ValueError, IndexError):
            continue
    return f"SR-{today}-{max_seq + 1:04d}"


def _calc_totals(items: list) -> tuple[Decimal, Decimal]:
    total_qty = Decimal("0")
    total_amt = Decimal("0")
    for item in items:
        qty = Decimal(str(item.quantity))
        price = Decimal(str(item.unit_price))
        total_qty += qty
        total_amt += qty * price
    return total_qty, total_amt


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def get_return(db: Session, return_id: int) -> SalesReturn | None:
    stmt = (
        select(SalesReturn)
        .options(
            selectinload(SalesReturn.items),
            joinedload(SalesReturn.customer),
            joinedload(SalesReturn.warehouse),
            joinedload(SalesReturn.order),
        )
        .where(SalesReturn.id == return_id, SalesReturn.is_deleted == 0)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_returns(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    customer_id: int | None = None,
    keyword: str | None = None,
) -> list[SalesReturn]:
    stmt = (
        select(SalesReturn)
        .options(
            selectinload(SalesReturn.items),
            joinedload(SalesReturn.customer),
            joinedload(SalesReturn.warehouse),
            joinedload(SalesReturn.order),
        )
        .where(SalesReturn.is_deleted == 0)
    )
    if status is not None:
        stmt = stmt.where(SalesReturn.status == status)
    if customer_id is not None:
        stmt = stmt.where(SalesReturn.customer_id == customer_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(SalesReturn.return_no.like(like), SalesReturn.reason.like(like))
        )
    stmt = stmt.order_by(SalesReturn.id.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().unique().all()


def get_returns_by_order_id(db: Session, order_id: int) -> list[SalesReturn]:
    stmt = (
        select(SalesReturn)
        .options(selectinload(SalesReturn.items))
        .where(
            SalesReturn.sales_order_id == order_id,
            SalesReturn.is_deleted == 0,
        )
    )
    return db.execute(stmt).scalars().all()


def create_return(
    db: Session, ret_in: SalesReturnCreate, created_by: int
) -> SalesReturn:
    """创建销售退货单（草稿）。

    - 校验销售订单存在且状态允许退货。
    - 校验退货商品属于该订单，退货数量不超过已出库数量。
    - unit_price 不传则取订单明细单价。
    """
    order = get_sales_order(db, ret_in.sales_order_id)
    if order is None:
        raise NotFoundException("销售订单不存在")
    if order.status not in ALLOWED_ORDER_STATUSES:
        raise ConflictException(
            f"销售订单状态为 {order.status}，仅已审核/部分出库/已完成订单可退货"
        )

    customer = db.execute(
        select(Customer).where(Customer.id == order.customer_id, Customer.is_deleted == 0)
    ).scalar_one_or_none()
    if customer is None:
        raise ValidationException("客户不存在或已删除")
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
            raise ValidationException(f"商品ID={item.product_id} 不在该销售订单中")
        if item.quantity > order_item.shipped_quantity:
            raise ValidationException(
                f"商品ID={item.product_id} 退货数量超过已出库数量"
                f"（退货={item.quantity}，已出库={order_item.shipped_quantity}）"
            )
        product_ids.append(item.product_id)

    if len(product_ids) != len(set(product_ids)):
        raise ValidationException("同一退货单内商品不能重复")

    return_no = _generate_no(db)

    total_qty = Decimal("0")
    total_amt = Decimal("0")
    db_items: list[SalesReturnItem] = []
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
            SalesReturnItem(
                product_id=item.product_id,
                quantity=qty,
                unit_price=price,
                amount=qty * price,
                batch_no=item.batch_no,
            )
        )

    ret = SalesReturn(
        return_no=return_no,
        sales_order_id=order.id,
        customer_id=order.customer_id,
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
    db: Session, return_id: int, ret_in: SalesReturnUpdate
) -> SalesReturn | None:
    """修改销售退货单（仅 draft 可改，明细全量替换）。"""
    ret = get_return(db, return_id)
    if ret is None:
        return None
    if ret.status != RETURN_STATUS_DRAFT:
        raise ConflictException(f"退货单状态为 {ret.status}，仅草稿可修改")

    order = get_sales_order(db, ret.sales_order_id)
    if order is None:
        raise NotFoundException("销售订单不存在")
    order_items_map = {item.product_id: item for item in order.items}

    product_ids = []
    for item in ret_in.items:
        order_item = order_items_map.get(item.product_id)
        if order_item is None:
            raise ValidationException(f"商品ID={item.product_id} 不在该销售订单中")
        if item.quantity > order_item.shipped_quantity:
            raise ValidationException(
                f"商品ID={item.product_id} 退货数量超过已出库数量"
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
            SalesReturnItem(
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
    """逻辑删除销售退货单（仅 draft 可删）。"""
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


def submit_return(db: Session, return_id: int) -> SalesReturn | None:
    ret = get_return(db, return_id)
    if ret is None:
        return None
    if ret.status != RETURN_STATUS_DRAFT:
        raise ConflictException(f"退货单状态为 {ret.status}，仅草稿可提交审核")
    ret.status = RETURN_STATUS_SUBMITTED
    db.commit()
    return get_return(db, ret.id)


def approve_return(db: Session, return_id: int, approved_by: int) -> SalesReturn | None:
    """审核通过：submitted -> approved，联动库存（商品由客户退回仓库，IN 流水）。

    入库 quantity 为正数，库存增加；无需校验库存充足性。
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
                quantity=abs(item.quantity),
                reference_type="SALES_RETURN",
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


def reject_return(db: Session, return_id: int) -> SalesReturn | None:
    ret = get_return(db, return_id)
    if ret is None:
        return None
    if ret.status != RETURN_STATUS_SUBMITTED:
        raise ConflictException(f"退货单状态为 {ret.status}，仅待审核可驳回")
    ret.status = RETURN_STATUS_REJECTED
    db.commit()
    return get_return(db, ret.id)
