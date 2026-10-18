"""供应商 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
所有查询默认过滤 is_deleted=0；删除为逻辑删除（is_deleted=1），不物理删除。
create/update 时校验 code 唯一性。
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.supplier import Supplier
from schemas.supplier import SupplierCreate, SupplierUpdate


def get_supplier(db: Session, supplier_id: int) -> Supplier | None:
    """根据 ID 查询单个未删除供应商。"""
    stmt = select(Supplier).where(
        Supplier.id == supplier_id,
        Supplier.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_suppliers(db: Session, skip: int = 0, limit: int = 100) -> list[Supplier]:
    """分页查询未删除供应商列表，按 id 升序排序。"""
    stmt = (
        select(Supplier)
        .where(Supplier.is_deleted == 0)
        .order_by(Supplier.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_supplier(db: Session, supplier: SupplierCreate) -> Supplier:
    """新增供应商。校验 code 唯一性，重复则抛出 400。"""
    existing = db.execute(
        select(Supplier).where(
            Supplier.code == supplier.code,
            Supplier.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="供应商编码已存在",
        )
    db_supplier = Supplier(**supplier.model_dump())
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier


def update_supplier(
    db: Session, supplier_id: int, supplier: SupplierUpdate
) -> Supplier | None:
    """根据 ID 更新供应商，未找到返回 None。仅更新传入的非空字段；
    若本次更新包含 code，校验新 code 不与其他记录重复（排除自身）。"""
    db_supplier = get_supplier(db, supplier_id)
    if db_supplier is None:
        return None
    update_data = supplier.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] is not None:
        existing = db.execute(
            select(Supplier).where(
                Supplier.code == update_data["code"],
                Supplier.id != supplier_id,
                Supplier.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="供应商编码已存在",
            )
    for field, value in update_data.items():
        setattr(db_supplier, field, value)
    db.commit()
    db.refresh(db_supplier)
    return db_supplier


def delete_supplier(db: Session, supplier_id: int) -> bool:
    """逻辑删除供应商（is_deleted=1），未找到返回 False。"""
    db_supplier = get_supplier(db, supplier_id)
    if db_supplier is None:
        return False
    db_supplier.is_deleted = 1
    db.commit()
    return True
