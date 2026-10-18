"""客户管理路由。

提供客户的增删改查接口，响应统一用 success()/error() 包装。
code 唯一性校验由 crud 层负责。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.response import error, success
from crud.customer import (
    create_customer,
    delete_customer,
    get_customer,
    get_customers,
    update_customer,
)
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
