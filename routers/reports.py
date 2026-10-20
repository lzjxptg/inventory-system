"""报表路由：库存流水汇总、低库存预警、采购/销售金额统计。

所有接口为只读查询，前缀 /api/v1/reports，需登录鉴权。
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, get_db
from core.exceptions import ValidationException
from core.excel_export import (
    build_excel_bytes,
    build_multi_sheet_excel_bytes,
    dated_filename,
    excel_response,
)
from core.permissions import require_permission
from core.response import success
from crud import reports as reports_crud
from models.user import User
from schemas.reports import (
    MovementReportItem,
    PurchaseSummaryData,
    SalesSummaryData,
)

router = APIRouter(prefix="/api/v1/reports", tags=["报表统计"])


@router.get("/inventory-movements")
def inventory_movements_report(
    product_id: int | None = Query(default=None, description="按商品ID筛选"),
    warehouse_id: int | None = Query(default=None, description="按仓库ID筛选"),
    movement_type: str | None = Query(default=None, description="流水类型：IN/OUT"),
    start_date: date | None = Query(default=None, description="起始日期 YYYY-MM-DD"),
    end_date: date | None = Query(default=None, description="截止日期 YYYY-MM-DD"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """库存流水汇总查询（带筛选与分页）。"""
    if start_date and end_date and start_date > end_date:
        raise ValidationException("起始日期不能大于截止日期")

    result = reports_crud.get_movements_report(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    items = [
        MovementReportItem.model_validate(m).model_dump()
        for m in result["items"]
    ]
    return success(data={
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
    })


@router.get("/low-stock-alerts")
def low_stock_alerts_report(
    warehouse_id: int | None = Query(default=None, description="按仓库ID筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """低库存预警列表（current_quantity <= 商品预警阈值，缺省阈值 10）。"""
    result = reports_crud.get_low_stock_alerts(
        db, warehouse_id=warehouse_id, page=page, page_size=page_size
    )
    return success(data=result)


@router.get("/low-stock-alerts/export", dependencies=[Depends(require_permission("reports:view"))])
def export_low_stock_alerts(
    warehouse_id: int | None = Query(default=None, description="按仓库ID筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出低库存预警 Excel。"""
    result = reports_crud.get_low_stock_alerts(
        db, warehouse_id=warehouse_id, page=1, page_size=100000
    )
    headers = ["商品ID", "商品名称", "仓库ID", "仓库名称", "当前库存", "预警阈值"]
    rows = [
        [
            it["product_id"], it["product_name"], it["warehouse_id"],
            it["warehouse_name"], float(it["current_quantity"]),
            float(it["alert_threshold"]),
        ]
        for it in result["items"]
    ]
    data = build_excel_bytes(headers, rows)
    return excel_response(data, dated_filename("低库存预警"))


@router.get("/purchase-summary")
def purchase_summary_report(
    start_date: date = Query(..., description="统计起始日期 YYYY-MM-DD"),
    end_date: date = Query(..., description="统计截止日期 YYYY-MM-DD"),
    supplier_id: int | None = Query(default=None, description="按供应商筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """采购金额统计（按日期范围、可选供应商）。"""
    if start_date > end_date:
        raise ValidationException("起始日期不能大于截止日期")

    data = reports_crud.get_purchase_summary(
        db, start_date=start_date, end_date=end_date, supplier_id=supplier_id
    )
    return success(data=PurchaseSummaryData.model_validate(data).model_dump())


@router.get("/purchase-summary/export", dependencies=[Depends(require_permission("reports:view"))])
def export_purchase_summary(
    start_date: date = Query(..., description="统计起始日期 YYYY-MM-DD"),
    end_date: date = Query(..., description="统计截止日期 YYYY-MM-DD"),
    supplier_id: int | None = Query(default=None, description="按供应商筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出采购统计 Excel（汇总 + 按供应商分组 两个 Sheet）。"""
    if start_date > end_date:
        raise ValidationException("起始日期不能大于截止日期")

    data = reports_crud.get_purchase_summary(
        db, start_date=start_date, end_date=end_date, supplier_id=supplier_id
    )

    summary_headers = ["采购订单数", "明细数", "总金额", "总数量"]
    summary_rows = [[
        data["total_orders"], data["total_items"],
        float(data["total_amount"]), float(data["total_quantity"]),
    ]]

    group_headers = ["供应商ID", "供应商名称", "订单数", "总金额"]
    group_rows = [
        [
            g["supplier_id"], g["supplier_name"], g["order_count"],
            float(g["total_amount"]),
        ]
        for g in data["by_supplier"]
    ]

    xlsx = build_multi_sheet_excel_bytes([
        ("汇总", summary_headers, summary_rows),
        ("按供应商分组", group_headers, group_rows),
    ])
    return excel_response(xlsx, dated_filename("采购统计"))


@router.get("/sales-summary")
def sales_summary_report(
    start_date: date = Query(..., description="统计起始日期 YYYY-MM-DD"),
    end_date: date = Query(..., description="统计截止日期 YYYY-MM-DD"),
    customer_id: int | None = Query(default=None, description="按客户筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """销售金额统计（按日期范围、可选客户）。"""
    if start_date > end_date:
        raise ValidationException("起始日期不能大于截止日期")

    data = reports_crud.get_sales_summary(
        db, start_date=start_date, end_date=end_date, customer_id=customer_id
    )
    return success(data=SalesSummaryData.model_validate(data).model_dump())


@router.get("/sales-summary/export", dependencies=[Depends(require_permission("reports:view"))])
def export_sales_summary(
    start_date: date = Query(..., description="统计起始日期 YYYY-MM-DD"),
    end_date: date = Query(..., description="统计截止日期 YYYY-MM-DD"),
    customer_id: int | None = Query(default=None, description="按客户筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出销售统计 Excel（汇总 + 按客户分组 两个 Sheet）。"""
    if start_date > end_date:
        raise ValidationException("起始日期不能大于截止日期")

    data = reports_crud.get_sales_summary(
        db, start_date=start_date, end_date=end_date, customer_id=customer_id
    )

    summary_headers = ["销售订单数", "明细数", "总金额", "总数量"]
    summary_rows = [[
        data["total_orders"], data["total_items"],
        float(data["total_amount"]), float(data["total_quantity"]),
    ]]

    group_headers = ["客户ID", "客户名称", "订单数", "总金额"]
    group_rows = [
        [
            g["customer_id"], g["customer_name"], g["order_count"],
            float(g["total_amount"]),
        ]
        for g in data["by_customer"]
    ]

    xlsx = build_multi_sheet_excel_bytes([
        ("汇总", summary_headers, summary_rows),
        ("按客户分组", group_headers, group_rows),
    ])
    return excel_response(xlsx, dated_filename("销售统计"))
