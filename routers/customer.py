"""客户管理路由。

提供客户的增删改查接口，响应统一用 success()/error() 包装。
code 唯一性校验由 crud 层负责。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.excel_export import build_excel_bytes, dated_filename, excel_response
from core.permissions import require_permission
from core.response import error, success
from crud.customer import (
    create_customer,
    delete_customer,
    get_customer,
    get_customers,
    update_customer,
)
from models.customer import Customer
from models.user import User
from schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/api/v1/customers", tags=["客户管理"])


@router.get("")
def list_customers(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """分页查询未删除客户列表。"""
    items = get_customers(db, skip=skip, limit=limit)
    return success(
        data=[CustomerResponse.model_validate(item).model_dump() for item in items]
    )


@router.get(
    "/export",
    dependencies=[Depends(require_permission("sales:view"))],
)
def export_customers(
    keyword: str | None = Query(default=None, description="按客户名称模糊筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出客户列表为 Excel（受相同筛选条件约束，不分页）。"""
    stmt = select(Customer).where(Customer.is_deleted == 0)
    if keyword:
        stmt = stmt.where(Customer.name.like(f"%{keyword}%"))
    stmt = stmt.order_by(Customer.id.asc())
    items = db.execute(stmt).scalars().all()

    headers = ["ID", "编码", "名称", "联系人", "电话", "地址", "创建时间"]
    rows = [
        [
            item.id,
            item.code,
            item.name,
            item.contact or "",
            item.phone or "",
            item.address or "",
            item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
        ]
        for item in items
    ]
    data = build_excel_bytes(headers, rows)
    return excel_response(data, dated_filename("客户列表"))


@router.get("/{customer_id}")
def read_customer(customer_id: int, db: Session = Depends(get_db)):
    """根据 ID 查询单个客户详情。"""
    item = get_customer(db, customer_id)
    if item is None:
        return error(code=404, msg="客户不存在")
    return success(data=CustomerResponse.model_validate(item).model_dump())


@router.post("")
def create_customer_api(customer: CustomerCreate, db: Session = Depends(get_db)):
    """新增客户（code 唯一性校验由 crud 层处理）。"""
    item = create_customer(db, customer)
    return success(
        data=CustomerResponse.model_validate(item).model_dump(),
        msg="创建成功",
    )


@router.put("/{customer_id}")
def update_customer_api(
    customer_id: int, customer: CustomerUpdate, db: Session = Depends(get_db)
):
    """根据 ID 更新客户。"""
    item = update_customer(db, customer_id, customer)
    if item is None:
        return error(code=404, msg="客户不存在")
    return success(
        data=CustomerResponse.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/{customer_id}")
def delete_customer_api(customer_id: int, db: Session = Depends(get_db)):
    """根据 ID 逻辑删除客户。"""
    ok = delete_customer(db, customer_id)
    if not ok:
        return error(code=404, msg="客户不存在")
    return success(msg="删除成功")
