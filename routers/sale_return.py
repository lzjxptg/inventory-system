"""销售退货管理路由。

对称于采购退货，审核通过时联动库存出库。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.excel_export import build_excel_bytes, dated_filename, excel_response
from core.permissions import require_permission
from core.response import error, success
from crud.sale_return import (
    approve_return,
    create_return,
    delete_return,
    get_return,
    list_returns,
    reject_return,
    submit_return,
    update_return,
)
from models.user import User
from schemas.sale_return import (
    SalesReturnCreate,
    SalesReturnResponse,
    SalesReturnUpdate,
)

router = APIRouter(prefix="/api/v1/sales-returns", tags=["销售退货"])


@router.post("", dependencies=[Depends(require_permission("sales_return:create"))])
def create_return_api(
    ret_in: SalesReturnCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建销售退货单（草稿）。"""
    item = create_return(db, ret_in, current_user.id)
    return success(
        data=SalesReturnResponse.model_validate(item).model_dump(),
        msg="创建销售退货单成功",
    )


@router.get("")
def list_returns_api(
    status: str | None = Query(default=None, description="按状态筛选"),
    customer_id: int | None = Query(default=None, description="按客户ID筛选"),
    keyword: str | None = Query(default=None, description="按退货单号/原因关键字筛选"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """分页查询销售退货单列表。"""
    items = list_returns(
        db, skip=skip, limit=limit, status=status, customer_id=customer_id, keyword=keyword
    )
    return success(
        data=[SalesReturnResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/export", dependencies=[Depends(require_permission("sales_return:view"))])
def export_returns(
    status: str | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出销售退货单 Excel。"""
    items = list_returns(
        db, skip=0, limit=100000, status=status, customer_id=customer_id, keyword=keyword
    )
    headers = [
        "ID", "退货单号", "销售订单号", "客户", "仓库", "状态",
        "总数量", "总金额", "退货原因", "创建时间",
    ]
    rows = [
        [
            r.id, r.return_no, r.order_no, r.customer_name, r.warehouse_name, r.status,
            float(r.total_quantity), float(r.total_amount), r.reason,
            r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        ]
        for r in items
    ]
    data = build_excel_bytes(headers, rows)
    return excel_response(data, dated_filename("销售退货单"))


@router.get("/{return_id}")
def get_return_api(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询销售退货单详情（含明细）。"""
    item = get_return(db, return_id)
    if item is None:
        return error(code=404, msg="销售退货单不存在")
    return success(data=SalesReturnResponse.model_validate(item).model_dump())


@router.put("/{return_id}")
def update_return_api(
    return_id: int,
    ret_in: SalesReturnUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改销售退货单（仅草稿可改）。"""
    item = update_return(db, return_id, ret_in)
    if item is None:
        return error(code=404, msg="销售退货单不存在")
    return success(
        data=SalesReturnResponse.model_validate(item).model_dump(),
        msg="修改销售退货单成功",
    )


@router.delete("/{return_id}")
def delete_return_api(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除销售退货单（仅草稿可删）。"""
    ok = delete_return(db, return_id)
    if not ok:
        return error(code=404, msg="销售退货单不存在")
    return success(msg="删除销售退货单成功")


@router.post("/{return_id}/submit")
def submit_return_api(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交审核：draft -> submitted。"""
    item = submit_return(db, return_id)
    if item is None:
        return error(code=404, msg="销售退货单不存在")
    return success(
        data=SalesReturnResponse.model_validate(item).model_dump(),
        msg="提交审核成功",
    )


@router.post("/{return_id}/approve", dependencies=[Depends(require_permission("sales_return:approve"))])
def approve_return_api(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审核通过：submitted -> approved，联动库存出库。"""
    item = approve_return(db, return_id, current_user.id)
    if item is None:
        return error(code=404, msg="销售退货单不存在")
    return success(
        data=SalesReturnResponse.model_validate(item).model_dump(),
        msg="审核通过成功",
    )


@router.post("/{return_id}/reject")
def reject_return_api(
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """驳回：submitted -> rejected。"""
    item = reject_return(db, return_id)
    if item is None:
        return error(code=404, msg="销售退货单不存在")
    return success(
        data=SalesReturnResponse.model_validate(item).model_dump(),
        msg="驳回成功",
    )
