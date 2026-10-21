"""客户门店 CRUD。

使用 SQLAlchemy 2.x 风格。
- 所有查询默认过滤 is_deleted=0；删除为逻辑删除。
- 同一客户下门店名称唯一（未删除范围内）。
- 设默认门店时，同客户其他门店 is_default 置 0。
"""

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.exceptions import NotFoundException, ValidationException
from models.customer import Customer
from models.customer_shop import CustomerShop
from schemas.customer_shop import CustomerShopCreate, CustomerShopUpdate


def get_shop(db: Session, shop_id: int) -> CustomerShop | None:
    """根据 ID 查询单个未删除门店。"""
    stmt = select(CustomerShop).where(
        CustomerShop.id == shop_id,
        CustomerShop.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_customer_shops_by_customer(
    db: Session, customer_id: int
) -> list[CustomerShop]:
    """按客户查询其下所有未删除门店（默认门店在前，再按 id 升序）。"""
    stmt = (
        select(CustomerShop)
        .where(
            CustomerShop.customer_id == customer_id,
            CustomerShop.is_deleted == 0,
        )
        .order_by(CustomerShop.is_default.desc(), CustomerShop.id.asc())
    )
    return db.execute(stmt).scalars().all()


def create_customer_shop(
    db: Session, shop: CustomerShopCreate
) -> CustomerShop:
    """新增门店。

    - 校验客户存在。
    - 校验同客户下门店名称不重复（未删除范围）。
    - 若设为默认，将同客户其他门店 is_default 置 0。
    """
    # 校验客户存在
    customer = db.execute(
        select(Customer).where(Customer.id == shop.customer_id, Customer.is_deleted == 0)
    ).scalar_one_or_none()
    if customer is None:
        raise NotFoundException("客户不存在或已删除")

    # 校验门店名称不重复
    existing = db.execute(
        select(CustomerShop).where(
            CustomerShop.customer_id == shop.customer_id,
            CustomerShop.shop_name == shop.shop_name,
            CustomerShop.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValidationException("该客户下已存在相同名称的门店")

    db_shop = CustomerShop(**shop.model_dump())
    db.add(db_shop)
    db.flush()

    # 若设为默认，同客户其他门店置为非默认
    if shop.is_default == 1:
        db.execute(
            update(CustomerShop)
            .where(
                CustomerShop.customer_id == shop.customer_id,
                CustomerShop.id != db_shop.id,
                CustomerShop.is_deleted == 0,
            )
            .values(is_default=0)
        )

    db.commit()
    db.refresh(db_shop)
    return db_shop


def update_customer_shop(
    db: Session, shop_id: int, shop: CustomerShopUpdate
) -> CustomerShop | None:
    """编辑门店，未找到返回 None。

    - 若改了 shop_name，校验同客户下不重复（排除自身）。
    - 若 is_default=1，同客户其他门店置 0。
    """
    db_shop = get_shop(db, shop_id)
    if db_shop is None:
        return None

    update_data = shop.model_dump(exclude_unset=True)

    if "shop_name" in update_data and update_data["shop_name"] is not None:
        existing = db.execute(
            select(CustomerShop).where(
                CustomerShop.customer_id == db_shop.customer_id,
                CustomerShop.shop_name == update_data["shop_name"],
                CustomerShop.id != shop_id,
                CustomerShop.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationException("该客户下已存在相同名称的门店")

    for field, value in update_data.items():
        setattr(db_shop, field, value)

    # 若本次设为默认，同客户其他门店置 0
    if update_data.get("is_default") == 1:
        db.execute(
            update(CustomerShop)
            .where(
                CustomerShop.customer_id == db_shop.customer_id,
                CustomerShop.id != shop_id,
                CustomerShop.is_deleted == 0,
            )
            .values(is_default=0)
        )

    db.commit()
    db.refresh(db_shop)
    return db_shop


def delete_customer_shop(db: Session, shop_id: int) -> bool:
    """逻辑删除门店，未找到返回 False。"""
    db_shop = get_shop(db, shop_id)
    if db_shop is None:
        return False
    db_shop.is_deleted = 1
    db.commit()
    return True


def set_default_shop(db: Session, shop_id: int) -> CustomerShop | None:
    """设为默认门店，同客户其他门店 is_default 置 0。未找到返回 None。"""
    db_shop = get_shop(db, shop_id)
    if db_shop is None:
        return None

    db.execute(
        update(CustomerShop)
        .where(
            CustomerShop.customer_id == db_shop.customer_id,
            CustomerShop.id != shop_id,
            CustomerShop.is_deleted == 0,
        )
        .values(is_default=0)
    )
    db_shop.is_default = 1
    db.commit()
    db.refresh(db_shop)
    return db_shop
