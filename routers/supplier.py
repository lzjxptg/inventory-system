"""供应商管理路由。

提供供应商的增删改查接口，响应统一用 success()/error() 包装。
code 唯一性校验由 crud 层负责。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.response import error, success
from crud.supplier import (
    create_supplier,
    delete_supplier,
    get_supplier,
    get_suppliers,
    update_supplier,
)
from schemas.supplier import SupplierCreate, SupplierResponse, SupplierUpdate

router = APIRouter(prefix="/api/v1/suppliers", tags=["供应商管理"])


@router.get("")
def list_suppliers(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """分页查询未删除供应商列表。"""
    items = get_suppliers(db, skip=skip, limit=limit)
    return success(
        data=[SupplierResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/{supplier_id}")
def read_supplier(supplier_id: int, db: Session = Depends(get_db)):
    """根据 ID 查询单个供应商详情。"""
    item = get_supplier(db, supplier_id)
    if item is None:
        return error(code=404, msg="供应商不存在")
    return success(data=SupplierResponse.model_validate(item).model_dump())


@router.post("")
def create_supplier_api(supplier: SupplierCreate, db: Session = Depends(get_db)):
    """新增供应商（code 唯一性校验由 crud 层处理）。"""
    item = create_supplier(db, supplier)
    return success(
        data=SupplierResponse.model_validate(item).model_dump(),
        msg="创建成功",
    )


@router.put("/{supplier_id}")
def update_supplier_api(
    supplier_id: int, supplier: SupplierUpdate, db: Session = Depends(get_db)
):
    """根据 ID 更新供应商。"""
    item = update_supplier(db, supplier_id, supplier)
    if item is None:
        return error(code=404, msg="供应商不存在")
    return success(
        data=SupplierResponse.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/{supplier_id}")
def delete_supplier_api(supplier_id: int, db: Session = Depends(get_db)):
    """根据 ID 逻辑删除供应商。"""
    ok = delete_supplier(db, supplier_id)
    if not ok:
        return error(code=404, msg="供应商不存在")
    return success(msg="删除成功")
