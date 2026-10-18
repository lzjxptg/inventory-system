"""仓库 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
所有查询默认过滤 is_deleted=0；删除为逻辑删除（is_deleted=1），不物理删除。
create/update 时校验 code 唯一性。
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.warehouse import Warehouse
from schemas.warehouse import WarehouseCreate, WarehouseUpdate


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    """根据 ID 查询单个未删除仓库。"""
    stmt = select(Warehouse).where(
        Warehouse.id == warehouse_id,
        Warehouse.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_warehouses(db: Session, skip: int = 0, limit: int = 100) -> list[Warehouse]:
    """分页查询未删除仓库列表，按 id 升序排序。"""
    stmt = (
        select(Warehouse)
        .where(Warehouse.is_deleted == 0)
        .order_by(Warehouse.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_warehouse(db: Session, warehouse: WarehouseCreate) -> Warehouse:
    """新增仓库。校验 code 唯一性，重复则抛出 400。"""
    existing = db.execute(
        select(Warehouse).where(
            Warehouse.code == warehouse.code,
            Warehouse.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仓库编码已存在",
        )
    db_warehouse = Warehouse(**warehouse.model_dump())
    db.add(db_warehouse)
    db.commit()
    db.refresh(db_warehouse)
    return db_warehouse


def update_warehouse(
    db: Session, warehouse_id: int, warehouse: WarehouseUpdate
) -> Warehouse | None:
    """根据 ID 更新仓库，未找到返回 None。仅更新传入的非空字段；
    若本次更新包含 code，校验新 code 不与其他记录重复（排除自身）。"""
    db_warehouse = get_warehouse(db, warehouse_id)
    if db_warehouse is None:
        return None
    update_data = warehouse.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] is not None:
        existing = db.execute(
            select(Warehouse).where(
                Warehouse.code == update_data["code"],
                Warehouse.id != warehouse_id,
                Warehouse.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="仓库编码已存在",
            )
    for field, value in update_data.items():
        setattr(db_warehouse, field, value)
    db.commit()
    db.refresh(db_warehouse)
    return db_warehouse


def delete_warehouse(db: Session, warehouse_id: int) -> bool:
    """逻辑删除仓库（is_deleted=1），未找到返回 False。"""
    db_warehouse = get_warehouse(db, warehouse_id)
    if db_warehouse is None:
        return False
    db_warehouse.is_deleted = 1
    db.commit()
    return True
