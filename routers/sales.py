"""销售管理路由。

提供销售订单（创建/列表/详情/修改/删除/提交/审核/取消）与
销售出库单（创建/列表/详情/确认/取消）接口。
所有端点需登录鉴权（main.py 统一加 PROTECTED）。
响应统一用 success()/error() 包装，业务异常由全局处理器接管。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.excel_export import build_excel_bytes, dated_filename, excel_response
from core.permissions import require_permission
from core.response import error, success
from crud.sales import (
    approve_order,
    cancel_order,
    cancel_out,
    confirm_out,
    create_order,
    create_out_from_order,
    delete_order,
    get_order,
    get_out,
    list_orders,
    list_outs,
    submit_order,
    update_order,
)
from models.user import User
from schemas.sales import (
    SalesOutCreate,
    SalesOutResponse,
    SalesOrderCreate,
    SalesOrderResponse,
    SalesOrderUpdate,
)

router = APIRouter(prefix="", tags=["销售管理"])


# ===========================================================================
# 销售订单
# ===========================================================================


@router.post("/orders")
def create_order_api(
    order_in: SalesOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建销售订单。"""
    item = create_order(db, order_in, current_user.id)
    return success(
        data=SalesOrderResponse.model_validate(item).model_dump(),
        msg="创建销售订单成功",
    )


@router.get("/orders")
def list_orders_api(
    status: str | None = Query(default=None, description="按订单状态筛选"),
    customer_id: int | None = Query(default=None, description="按客户ID筛选"),
    keyword: str | None = Query(default=None, description="按订单号/备注关键字筛选"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询销售订单列表。"""
    items = list_orders(
        db, skip=skip, limit=limit, status=status, customer_id=customer_id, keyword=keyword
    )
    return success(
        data=[SalesOrderResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/orders/export", dependencies=[Depends(require_permission("sales:view"))])
def export_orders(
    status: str | None = Query(default=None, description="按订单状态筛选"),
    customer_id: int | None = Query(default=None, description="按客户ID筛选"),
    keyword: str | None = Query(default=None, description="按订单号/备注关键字筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出销售订单 Excel（受相同筛选条件约束，不分页）。"""
    items = list_orders(
        db, skip=0, limit=100000, status=status, customer_id=customer_id, keyword=keyword
    )
    headers = [
        "ID", "订单号", "客户", "仓库", "状态", "总数量", "总金额", "备注", "创建时间",
    ]
    rows = [
        [
            o.id, o.order_no, o.customer_name, o.warehouse_name, o.status,
            float(o.total_quantity), float(o.total_amount), o.remark,
            o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
        ]
        for o in items
    ]
    data = build_excel_bytes(headers, rows)
    return excel_response(data, dated_filename("销售订单"))


@router.get("/orders/{order_id}")
def get_order_api(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询销售订单详情（含明细）。"""
    item = get_order(db, order_id)
    if item is None:
        return error(code=404, msg="销售订单不存在")
    return success(data=SalesOrderResponse.model_validate(item).model_dump())


@router.put("/orders/{order_id}")
def update_order_api(
    order_id: int,
    order_in: SalesOrderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改销售订单（仅草稿可改，明细全量替换）。"""
    item = update_order(db, order_id, order_in)
    if item is None:
        return error(code=404, msg="销售订单不存在")
    return success(
        data=SalesOrderResponse.model_validate(item).model_dump(),
        msg="修改销售订单成功",
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
        return error(code=404, msg="销售订单不存在")
    return success(
        data=SalesOrderResponse.model_validate(item).model_dump(),
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
        return error(code=404, msg="销售订单不存在")
    return success(
        data=SalesOrderResponse.model_validate(item).model_dump(),
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
        return error(code=404, msg="销售订单不存在")
    return success(
        data=SalesOrderResponse.model_validate(item).model_dump(),
        msg="取消订单成功",
    )


@router.delete("/orders/{order_id}")
def delete_order_api(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """逻辑删除销售订单（仅草稿可删）。"""
    ok = delete_order(db, order_id)
    if not ok:
        return error(code=404, msg="销售订单不存在")
    return success(msg="删除销售订单成功")


# ===========================================================================
# 销售出库单
# ===========================================================================


@router.post("/orders/{order_id}/outs")
def create_out_api(
    order_id: int,
    out_data: SalesOutCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于销售订单创建出库单（草稿）。"""
    item = create_out_from_order(db, order_id, out_data, current_user.id)
    return success(
        data=SalesOutResponse.model_validate(item).model_dump(),
        msg="创建销售出库单成功",
    )


@router.get("/outs")
def list_outs_api(
    status: str | None = Query(default=None, description="按出库单状态筛选"),
    sales_order_id: int | None = Query(default=None, description="按销售订单ID筛选"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询销售出库单列表。"""
    items = list_outs(
        db, skip=skip, limit=limit, status=status, sales_order_id=sales_order_id
    )
    return success(
        data=[SalesOutResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/outs/{out_id}")
def get_out_api(
    out_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询销售出库单详情（含明细）。"""
    item = get_out(db, out_id)
    if item is None:
        return error(code=404, msg="销售出库单不存在")
    return success(data=SalesOutResponse.model_validate(item).model_dump())


@router.post("/outs/{out_id}/confirm")
def confirm_out_api(
    out_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """确认出库（联动库存，核心接口）。"""
    item = confirm_out(db, out_id, current_user.id)
    if item is None:
        return error(code=404, msg="销售出库单不存在")
    return success(
        data=SalesOutResponse.model_validate(item).model_dump(),
        msg="确认出库成功",
    )


@router.post("/outs/{out_id}/cancel")
def cancel_out_api(
    out_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """取消出库单（仅草稿可取消）。"""
    item = cancel_out(db, out_id)
    if item is None:
        return error(code=404, msg="销售出库单不存在")
    return success(
        data=SalesOutResponse.model_validate(item).model_dump(),
        msg="取消出库单成功",
    )
