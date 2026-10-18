"""库存 CRUD。

提供库存余额查询、库存流水查询、入库/出库（create_stock_movement）、
盘点调整（adjust_inventory）等数据访问函数。

要点：
- 流水写入与余额更新在同一 session 事务内，失败回滚。
- 出库时校验库存充足，不足抛 ValidationException(40001)。
- 新增/调整前校验商品与仓库外键存在且未逻辑删除。
- 查询默认过滤 is_deleted=0。
- 使用 joinedload 预加载关联对象，供响应 schema 读取名称字段。
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from core.exceptions import ValidationException
from models.inventory import InventoryBalance, StockMovement
from models.product import Product
from models.warehouse import Warehouse
from schemas.inventory import StockMovementCreate


# ---------------------------------------------------------------------------
# 库存余额
# ---------------------------------------------------------------------------


def get_inventory_balances(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    product_id: int | None = None,
    warehouse_id: int | None = None,
) -> list[InventoryBalance]:
    """分页查询库存余额列表，支持按商品/仓库筛选。"""
    stmt = select(InventoryBalance).where(InventoryBalance.is_deleted == 0)
    if product_id is not None:
        stmt = stmt.where(InventoryBalance.product_id == product_id)
    if warehouse_id is not None:
        stmt = stmt.where(InventoryBalance.warehouse_id == warehouse_id)
    stmt = (
        stmt.options(joinedload(InventoryBalance.product), joinedload(InventoryBalance.warehouse))
        .order_by(InventoryBalance.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().unique().all()


def get_inventory_balance(
    db: Session, product_id: int, warehouse_id: int
) -> InventoryBalance | None:
    """查询某商品在某仓库的库存余额（未删除）。"""
    stmt = (
        select(InventoryBalance)
        .options(joinedload(InventoryBalance.product), joinedload(InventoryBalance.warehouse))
        .where(
            InventoryBalance.product_id == product_id,
            InventoryBalance.warehouse_id == warehouse_id,
            InventoryBalance.is_deleted == 0,
        )
    )
    return db.execute(stmt).scalar_one_or_none()


# ---------------------------------------------------------------------------
# 库存流水
# ---------------------------------------------------------------------------


def get_stock_movements(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    product_id: int | None = None,
    warehouse_id: int | None = None,
    movement_type: str | None = None,
) -> list[StockMovement]:
    """分页查询库存流水列表，支持按商品/仓库/流水类型筛选，按 id 倒序。"""
    stmt = select(StockMovement).where(StockMovement.is_deleted == 0)
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if warehouse_id is not None:
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
    if movement_type is not None:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
    stmt = (
        stmt.options(
            joinedload(StockMovement.product),
            joinedload(StockMovement.warehouse),
            joinedload(StockMovement.operator),
        )
        .order_by(StockMovement.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().unique().all()


# ---------------------------------------------------------------------------
# 入库 / 出库
# ---------------------------------------------------------------------------


def _check_product_and_warehouse(db: Session, product_id: int, warehouse_id: int) -> None:
    """校验商品与仓库存在且未逻辑删除，不存在则抛 ValidationException(40001)。"""
    product = db.execute(
        select(Product).where(Product.id == product_id, Product.is_deleted == 0)
    ).scalar_one_or_none()
    if product is None:
        raise ValidationException("商品不存在或已删除")
    warehouse = db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.is_deleted == 0)
    ).scalar_one_or_none()
    if warehouse is None:
        raise ValidationException("仓库不存在或已删除")


def create_stock_movement(
    db: Session, movement: StockMovementCreate, operator_id: int
) -> StockMovement:
    """创建库存流水并同步更新余额（入库/出库通用）。

    - quantity 正负由调用方决定（入库为正、出库为负）。
    - 出库（quantity < 0）时校验当前余额 >= abs(quantity)，不足抛 400。
    - 余额记录不存在则新建，存在则累加 quantity。
    - 流水写入与余额更新在同一事务内，异常时由调用方 session 回滚。
    """
    _check_product_and_warehouse(db, movement.product_id, movement.warehouse_id)

    # 查询该 (product_id, warehouse_id) 的余额记录
    balance = db.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == movement.product_id,
            InventoryBalance.warehouse_id == movement.warehouse_id,
            InventoryBalance.is_deleted == 0,
        )
    ).scalar_one_or_none()

    # 出库校验库存充足
    if movement.quantity < 0:
        current_qty = balance.current_quantity if balance is not None else Decimal("0")
        if current_qty < abs(movement.quantity):
            raise ValidationException(f"库存不足，当前库存为 {current_qty}")

    # 更新或创建余额
    if balance is None:
        balance = InventoryBalance(
            product_id=movement.product_id,
            warehouse_id=movement.warehouse_id,
            current_quantity=movement.quantity,
        )
        db.add(balance)
    else:
        balance.current_quantity += movement.quantity

    # 写入流水
    db_movement = StockMovement(
        product_id=movement.product_id,
        warehouse_id=movement.warehouse_id,
        movement_type=movement.movement_type,
        quantity=movement.quantity,
        reference_type=movement.reference_type,
        reference_id=movement.reference_id,
        operator_id=operator_id,
        remark=movement.remark,
    )
    db.add(db_movement)

    db.commit()
    db.refresh(db_movement)
    return db_movement


# ---------------------------------------------------------------------------
# 盘点调整
# ---------------------------------------------------------------------------


def adjust_inventory(
    db: Session,
    product_id: int,
    warehouse_id: int,
    new_quantity: Decimal,
    operator_id: int,
    remark: str | None = None,
) -> StockMovement:
    """盘点调整：将库存余额直接设为 new_quantity，并写入一条 ADJUST 流水。

    差值 = new_quantity - current_quantity，流水 quantity 取该差值
    （盘盈为正、盘亏为负）。流水与余额更新在同一事务内。
    """
    _check_product_and_warehouse(db, product_id, warehouse_id)

    balance = db.execute(
        select(InventoryBalance).where(
            InventoryBalance.product_id == product_id,
            InventoryBalance.warehouse_id == warehouse_id,
            InventoryBalance.is_deleted == 0,
        )
    ).scalar_one_or_none()

    current_qty = balance.current_quantity if balance is not None else Decimal("0")
    diff = new_quantity - current_qty

    # 更新或创建余额
    if balance is None:
        balance = InventoryBalance(
            product_id=product_id,
            warehouse_id=warehouse_id,
            current_quantity=new_quantity,
        )
        db.add(balance)
    else:
        balance.current_quantity = new_quantity

    # 写入盘点调整流水
    db_movement = StockMovement(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type="ADJUST",
        quantity=diff,
        reference_type="ADJUST",
        operator_id=operator_id,
        remark=remark,
    )
    db.add(db_movement)

    db.commit()
    db.refresh(db_movement)
    return db_movement


# ---------------------------------------------------------------------------
# 批量入库（供采购等业务模块调用，只 flush 不 commit，由调用方统一提交）
# ---------------------------------------------------------------------------


def create_stock_movements(
    db: Session, movements: list[StockMovementCreate], operator_id: int
) -> list[StockMovement]:
    """批量创建库存流水并同步更新余额（供业务单据调用）。

    与 ``create_stock_movement`` 的区别：
    - 接受多条流水，逐条更新余额与写流水，最后只 ``db.flush()``，**不 commit**。
    - 由调用方（如采购确认入库）在同一事务内统一 commit，保证业务单据与库存原子一致。
    - 校验失败抛 ``ValidationException(40001)``，其余异常原样抛出由调用方事务回滚。

    Args:
        db: 数据库会话。
        movements: 流水创建请求列表（quantity 正负由调用方决定，入库为正）。
        operator_id: 操作人ID。

    Returns:
        新建的 StockMovement ORM 对象列表。
    """
    if not movements:
        raise ValidationException("流水列表不能为空")

    created: list[StockMovement] = []
    for movement in movements:
        # 校验商品与仓库存在且未逻辑删除（不存在抛 ValidationException）
        _check_product_and_warehouse(db, movement.product_id, movement.warehouse_id)

        # 出库（quantity < 0）校验库存充足
        if movement.quantity < 0:
            balance = db.execute(
                select(InventoryBalance).where(
                    InventoryBalance.product_id == movement.product_id,
                    InventoryBalance.warehouse_id == movement.warehouse_id,
                    InventoryBalance.is_deleted == 0,
                )
            ).scalar_one_or_none()
            current_qty = balance.current_quantity if balance is not None else Decimal("0")
            if current_qty < abs(movement.quantity):
                raise ValidationException(f"商品ID={movement.product_id} 库存不足")

        # 查询该 (product_id, warehouse_id) 的余额记录
        balance = db.execute(
            select(InventoryBalance).where(
                InventoryBalance.product_id == movement.product_id,
                InventoryBalance.warehouse_id == movement.warehouse_id,
                InventoryBalance.is_deleted == 0,
            )
        ).scalar_one_or_none()

        # 更新或创建余额
        if balance is None:
            balance = InventoryBalance(
                product_id=movement.product_id,
                warehouse_id=movement.warehouse_id,
                current_quantity=movement.quantity,
            )
            db.add(balance)
        else:
            balance.current_quantity += movement.quantity

        # 写入流水
        db_movement = StockMovement(
            product_id=movement.product_id,
            warehouse_id=movement.warehouse_id,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            operator_id=operator_id,
            remark=movement.remark,
        )
        db.add(db_movement)
        created.append(db_movement)

    # 只 flush 不 commit，由调用方统一提交事务
    db.flush()
    return created
