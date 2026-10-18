"""计量单位 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
所有查询默认过滤 is_deleted=0；删除为逻辑删除（is_deleted=1），不物理删除。
create/update 时校验 code 唯一性。
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.unit import Unit
from schemas.unit import UnitCreate, UnitUpdate


def get_unit(db: Session, unit_id: int) -> Unit | None:
    """根据 ID 查询单个未删除单位。"""
    stmt = select(Unit).where(
        Unit.id == unit_id,
        Unit.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_units(db: Session, skip: int = 0, limit: int = 100) -> list[Unit]:
    """分页查询未删除单位列表，按 sort 升序、id 升序排序。"""
    stmt = (
        select(Unit)
        .where(Unit.is_deleted == 0)
        .order_by(Unit.sort.asc(), Unit.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_unit(db: Session, unit: UnitCreate) -> Unit:
    """新增单位。校验 code 唯一性，重复则抛出 400。"""
    if unit.code is not None:
        existing = db.execute(
            select(Unit).where(
                Unit.code == unit.code,
                Unit.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="单位编码已存在",
            )
    db_unit = Unit(**unit.model_dump())
    db.add(db_unit)
    db.commit()
    db.refresh(db_unit)
    return db_unit


def update_unit(
    db: Session, unit_id: int, unit: UnitUpdate
) -> Unit | None:
    """根据 ID 更新单位，未找到返回 None。仅更新传入的非空字段；
    若本次更新包含 code，校验新 code 不与其他记录重复（排除自身）。"""
    db_unit = get_unit(db, unit_id)
    if db_unit is None:
        return None
    update_data = unit.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] is not None:
        existing = db.execute(
            select(Unit).where(
                Unit.code == update_data["code"],
                Unit.id != unit_id,
                Unit.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="单位编码已存在",
            )
    for field, value in update_data.items():
        setattr(db_unit, field, value)
    db.commit()
    db.refresh(db_unit)
    return db_unit


def delete_unit(db: Session, unit_id: int) -> bool:
    """逻辑删除单位（is_deleted=1），未找到返回 False。"""
    db_unit = get_unit(db, unit_id)
    if db_unit is None:
        return False
    db_unit.is_deleted = 1
    db.commit()
    return True
