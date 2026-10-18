"""仓库管理路由。

提供仓库的增删改查接口，响应统一用 success()/error() 包装。
code 唯一性校验由 crud 层负责。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.response import error, success
from crud.warehouse import (
    create_warehouse,
    delete_warehouse,
    get_warehouse,
    get_warehouses,
    update_warehouse,
)
from schemas.warehouse import WarehouseCreate, WarehouseResponse, WarehouseUpdate

router = APIRouter(prefix="/api/v1/warehouses", tags=["仓库管理"])


@router.get("")
def list_warehouses(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """分页查询未删除仓库列表。"""
    items = get_warehouses(db, skip=skip, limit=limit)
    return success(
        data=[WarehouseResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/{warehouse_id}")
def read_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    """根据 ID 查询单个仓库详情。"""
    item = get_warehouse(db, warehouse_id)
    if item is None:
        return error(code=404, msg="仓库不存在")
    return success(data=WarehouseResponse.model_validate(item).model_dump())


@router.post("")
def create_warehouse_api(warehouse: WarehouseCreate, db: Session = Depends(get_db)):
    """新增仓库（code 唯一性校验由 crud 层处理）。"""
    item = create_warehouse(db, warehouse)
    return success(
        data=WarehouseResponse.model_validate(item).model_dump(),
        msg="创建成功",
    )


@router.put("/{warehouse_id}")
def update_warehouse_api(
    warehouse_id: int, warehouse: WarehouseUpdate, db: Session = Depends(get_db)
):
    """根据 ID 更新仓库。"""
    item = update_warehouse(db, warehouse_id, warehouse)
    if item is None:
        return error(code=404, msg="仓库不存在")
    return success(
        data=WarehouseResponse.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/{warehouse_id}")
def delete_warehouse_api(warehouse_id: int, db: Session = Depends(get_db)):
    """根据 ID 逻辑删除仓库。"""
    ok = delete_warehouse(db, warehouse_id)
    if not ok:
        return error(code=404, msg="仓库不存在")
    return success(msg="删除成功")
