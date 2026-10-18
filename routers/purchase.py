"""采购管理路由。

提供采购订单（创建/列表/详情/修改/删除/提交/审核/取消）与
采购入库单（创建/列表/详情/确认/取消）接口。
所有端点需登录鉴权（main.py 统一加 PROTECTED）。
响应统一用 success()/error() 包装，业务异常由全局处理器接管。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.response import error, success
from crud.purchase import (
    approve_order,
    cancel_in,
    cancel_order,
    confirm_in,
    create_in_from_order,
    create_order,
    delete_order,
    get_in,
    get_order,
    list_ins,
    list_orders,
    submit_order,
    update_order,
)
from models.user import User
from schemas.purchase import (
    PurchaseInCreate,
    PurchaseInResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)

router = APIRouter(prefix="", tags=["采购管理"])


# ===========================================================================
# 采购订单
# ===========================================================================


@router.post("/orders")
def create_order_api(
    order_in: PurchaseOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建采购订单。"""
    item = create_order(db, order_in, current_user.id)
    return success(
        data=PurchaseOrderResponse.model_validate(item).model_dump(),
        msg="创建采购订单成功",
    )


@router.get("/orders")
def list_orders_api(
    status: str | None = Query(default=None, description="按订单状态筛选"),
    supplier_id: int | None = Query(default=None, description="按供应商ID筛选"),
    keyword: str | None = Query(default=None, description="按订单号/备注关键字筛选"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询采购订单列表。"""
    items = list_orders(
        db, skip=skip, limit=limit, status=status, supplier_id=supplier_id, keyword=keyword
    )
    return success(
        data=[PurchaseOrderResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/orders/{order_id}")
def get_order_api(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询采购订单详情（含明细）。"""
    item = get_order(db, order_id)
    if item is None:
        return error(code=404, msg="采购订单不存在")
    return success(data=PurchaseOrderResponse.model_validate(item).model_dump())


@router.put("/orders/{order_id}")
def update_order_api(
    order_id: int,
    order_in: PurchaseOrderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改采购订单（仅草稿可改，明细全量替换）。"""
    item = update_order(db, order_id, order_in)
    if item is None:
        return error(code=404, msg="采购订单不存在")
    return success(
        data=PurchaseOrderResponse.model_validate(item).model_dump(),
        msg="修改采购订单成功",
    )


@router.post("/orders/{order_id}/submit")
def submit_order_api(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交审核：draft -> submitted。"""
    item = submit_order(db, order_id)
    if item is None:
        return error(code=404, msg="采购订单不存在")
    return success(
        data=PurchaseOrderResponse.model_validate(item).model_dump(),
        msg="提交审核成功",
    )


@router.post("/orders/{order_id}/approve")
def approve_order_api(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审核通过：submitted -> approved。"""
    item = approve_order(db, order_id, current_user.id)
    if item is None:
        return error(code=404, msg="采购订单不存在")
    return success(
        data=PurchaseOrderResponse.model_validate(item).model_dump(),
        msg="审核通过成功",
    )


@router.post("/orders/{order_id}/cancel")
def cancel_order_api(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消订单（已完成不可取消）。"""
    item = cancel_order(db, order_id)
    if item is None:
        return error(code=404, msg="采购订单不存在")
    return success(
        data=PurchaseOrderResponse.model_validate(item).model_dump(),
        msg="取消订单成功",
    )


@router.delete("/orders/{order_id}")
def delete_order_api(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """逻辑删除采购订单（仅草稿可删）。"""
    ok = delete_order(db, order_id)
    if not ok:
        return error(code=404, msg="采购订单不存在")
    return success(msg="删除采购订单成功")


# ===========================================================================
# 采购入库单
# ===========================================================================


@router.post("/orders/{order_id}/ins")
def create_in_api(
    order_id: int,
    in_data: PurchaseInCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于采购订单创建入库单（草稿）。"""
    item = create_in_from_order(db, order_id, in_data, current_user.id)
    return success(
        data=PurchaseInResponse.model_validate(item).model_dump(),
        msg="创建采购入库单成功",
    )


@router.get("/ins")
def list_ins_api(
    status: str | None = Query(default=None, description="按入库单状态筛选"),
    purchase_order_id: int | None = Query(default=None, description="按采购订单ID筛选"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询采购入库单列表。"""
    items = list_ins(
        db, skip=skip, limit=limit, status=status, purchase_order_id=purchase_order_id
    )
    return success(
        data=[PurchaseInResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/ins/{in_id}")
def get_in_api(
    in_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询采购入库单详情（含明细）。"""
    item = get_in(db, in_id)
    if item is None:
        return error(code=404, msg="采购入库单不存在")
    return success(data=PurchaseInResponse.model_validate(item).model_dump())


@router.post("/ins/{in_id}/confirm")
def confirm_in_api(
    in_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """确认入库（联动库存，核心接口）。"""
    item = confirm_in(db, in_id, current_user.id)
    if item is None:
        return error(code=404, msg="采购入库单不存在")
    return success(
        data=PurchaseInResponse.model_validate(item).model_dump(),
        msg="确认入库成功",
    )


@router.post("/ins/{in_id}/cancel")
def cancel_in_api(
    in_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消入库单（仅草稿可取消）。"""
    item = cancel_in(db, in_id)
    if item is None:
        return error(code=404, msg="采购入库单不存在")
    return success(
        data=PurchaseInResponse.model_validate(item).model_dump(),
        msg="取消入库单成功",
    )
