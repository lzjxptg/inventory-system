"""客户 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
所有查询默认过滤 is_deleted=0；删除为逻辑删除（is_deleted=1），不物理删除。
create/update 时校验 code 唯一性。
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.customer import Customer
from schemas.customer import CustomerCreate, CustomerUpdate


def get_customer(db: Session, customer_id: int) -> Customer | None:
    """根据 ID 查询单个未删除客户。"""
    stmt = select(Customer).where(
        Customer.id == customer_id,
        Customer.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_customers(db: Session, skip: int = 0, limit: int = 100) -> list[Customer]:
    """分页查询未删除客户列表，按 id 升序排序。"""
    stmt = (
        select(Customer)
        .where(Customer.is_deleted == 0)
        .order_by(Customer.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_customer(db: Session, customer: CustomerCreate) -> Customer:
    """新增客户。校验 code 唯一性，重复则抛出 400。"""
    existing = db.execute(
        select(Customer).where(
            Customer.code == customer.code,
            Customer.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="客户编码已存在",
        )
    db_customer = Customer(**customer.model_dump())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


def update_customer(
    db: Session, customer_id: int, customer: CustomerUpdate
) -> Customer | None:
    """根据 ID 更新客户，未找到返回 None。仅更新传入的非空字段；
    若本次更新包含 code，校验新 code 不与其他记录重复（排除自身）。"""
    db_customer = get_customer(db, customer_id)
    if db_customer is None:
        return None
    update_data = customer.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"] is not None:
        existing = db.execute(
            select(Customer).where(
                Customer.code == update_data["code"],
                Customer.id != customer_id,
                Customer.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="客户编码已存在",
            )
    for field, value in update_data.items():
        setattr(db_customer, field, value)
    db.commit()
    db.refresh(db_customer)
    return db_customer


def delete_customer(db: Session, customer_id: int) -> bool:
    """逻辑删除客户（is_deleted=1），未找到返回 False。"""
    db_customer = get_customer(db, customer_id)
    if db_customer is None:
        return False
    db_customer.is_deleted = 1
    db.commit()
    return True
