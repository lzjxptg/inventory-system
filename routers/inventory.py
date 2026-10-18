"""库存管理路由。

提供入库、出库、盘点调整、库存余额查询、库存流水查询接口。
所有端点需登录鉴权，operator_id 从 JWT token 的 current_user.id 取。
响应统一用 success()/error() 包装。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.response import error, success
from crud.inventory import (
    adjust_inventory,
    create_stock_movement,
    get_inventory_balance,
    get_inventory_balances,
    get_stock_movements,
)
from models.user import User
from schemas.inventory import (
    InventoryAdjustRequest,
    InventoryBalanceOut,
    StockMovementCreate,
    StockMovementOut,
)

router = APIRouter(prefix="/api/v1/inventory", tags=["库存"])


@router.post("/in")
def stock_in(
    movement: StockMovementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """入库：强制 movement_type='IN'，quantity 取绝对值。"""
    movement.movement_type = "IN"
    movement.quantity = abs(movement.quantity)
    item = create_stock_movement(db, movement, current_user.id)
    return success(
        data=StockMovementOut.model_validate(item).model_dump(),
        msg="入库成功",
    )


@router.post("/out")
def stock_out(
    movement: StockMovementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """出库：强制 movement_type='OUT'，quantity 存为负数，库存不足由 crud 层校验。"""
    movement.movement_type = "OUT"
    movement.quantity = -abs(movement.quantity)
    item = create_stock_movement(db, movement, current_user.id)
    return success(
        data=StockMovementOut.model_validate(item).model_dump(),
        msg="出库成功",
    )


@router.post("/adjust")
def stock_adjust(
    req: InventoryAdjustRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """盘点调整：将库存余额直接设为 new_quantity，并写入 ADJUST 流水。"""
    item = adjust_inventory(
        db,
        product_id=req.product_id,
        warehouse_id=req.warehouse_id,
        new_quantity=req.new_quantity,
        operator_id=current_user.id,
        remark=req.remark,
    )
    return success(
        data=StockMovementOut.model_validate(item).model_dump(),
        msg="盘点调整成功",
    )


@router.get("/balances")
def list_inventory_balances(
    product_id: int | None = Query(default=None, description="按商品ID筛选"),
    warehouse_id: int | None = Query(default=None, description="按仓库ID筛选"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询库存余额列表，支持按商品/仓库筛选。"""
    items = get_inventory_balances(
        db, skip=skip, limit=limit, product_id=product_id, warehouse_id=warehouse_id
    )
    return success(
        data=[InventoryBalanceOut.model_validate(item).model_dump() for item in items]
    )


@router.get("/movements")
def list_stock_movements(
    product_id: int | None = Query(default=None, description="按商品ID筛选"),
    warehouse_id: int | None = Query(default=None, description="按仓库ID筛选"),
    movement_type: str | None = Query(default=None, description="按流水类型筛选"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询库存流水列表，支持按商品/仓库/流水类型筛选。"""
    items = get_stock_movements(
        db,
        skip=skip,
        limit=limit,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
    )
    return success(
        data=[StockMovementOut.model_validate(item).model_dump() for item in items]
    )


@router.get("/balances/{product_id}/{warehouse_id}")
def read_inventory_balance(
    product_id: int,
    warehouse_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询某商品在某仓库的库存余额。"""
    item = get_inventory_balance(db, product_id, warehouse_id)
    if item is None:
        return error(code=404, msg="该商品在该仓库暂无库存记录")
    return success(data=InventoryBalanceOut.model_validate(item).model_dump())
