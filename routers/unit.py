"""计量单位管理路由。

提供计量单位的增删改查接口，响应统一用 success()/error() 包装。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.response import error, success
from crud.unit import (
    create_unit,
    delete_unit,
    get_unit,
    get_units,
    update_unit,
)
from schemas.unit import UnitCreate, UnitResponse, UnitUpdate

router = APIRouter(prefix="/api/v1/units", tags=["计量单位管理"])


@router.get("")
def list_units(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """分页查询未删除计量单位列表。"""
    items = get_units(db, skip=skip, limit=limit)
    return success(
        data=[UnitResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/{unit_id}")
def read_unit(unit_id: int, db: Session = Depends(get_db)):
    """根据 ID 查询单个计量单位详情。"""
    item = get_unit(db, unit_id)
    if item is None:
        return error(code=404, msg="计量单位不存在")
    return success(data=UnitResponse.model_validate(item).model_dump())


@router.post("")
def create_unit_api(unit: UnitCreate, db: Session = Depends(get_db)):
    """新增计量单位。"""
    item = create_unit(db, unit)
    return success(
        data=UnitResponse.model_validate(item).model_dump(),
        msg="创建成功",
    )


@router.put("/{unit_id}")
def update_unit_api(
    unit_id: int, unit: UnitUpdate, db: Session = Depends(get_db)
):
    """根据 ID 更新计量单位。"""
    item = update_unit(db, unit_id, unit)
    if item is None:
        return error(code=404, msg="计量单位不存在")
    return success(
        data=UnitResponse.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/{unit_id}")
def delete_unit_api(unit_id: int, db: Session = Depends(get_db)):
    """根据 ID 逻辑删除计量单位。"""
    ok = delete_unit(db, unit_id)
    if not ok:
        return error(code=404, msg="计量单位不存在")
    return success(msg="删除成功")
