"""商品 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
所有查询默认过滤 is_deleted=0；删除为逻辑删除（is_deleted=1），不物理删除。
create/update 时校验 sku 唯一性及 category_id / unit_id 外键存在性。
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.category import Category
from models.product import Product
from models.unit import Unit
from schemas.product import ProductCreate, ProductUpdate


def get_product(db: Session, product_id: int) -> Product | None:
    """根据 ID 查询单个未删除商品。"""
    stmt = select(Product).where(
        Product.id == product_id,
        Product.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_products(db: Session, skip: int = 0, limit: int = 100) -> list[Product]:
    """分页查询未删除商品列表，按 id 升序排序。"""
    stmt = (
        select(Product)
        .where(Product.is_deleted == 0)
        .order_by(Product.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_product(db: Session, product: ProductCreate) -> Product:
    """新增商品。校验 sku 唯一性及 category_id / unit_id 外键存在性。"""
    # sku 唯一性校验
    existing = db.execute(
        select(Product).where(
            Product.sku == product.sku,
            Product.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="商品编码已存在",
        )
    # category_id 外键校验（可空）
    if product.category_id is not None:
        category = db.execute(
            select(Category).where(
                Category.id == product.category_id,
                Category.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="分类不存在或已删除",
            )
    # unit_id 外键校验
    unit = db.execute(
        select(Unit).where(
            Unit.id == product.unit_id,
            Unit.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if unit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="计量单位不存在或已删除",
        )
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


def update_product(
    db: Session, product_id: int, product: ProductUpdate
) -> Product | None:
    """根据 ID 更新商品，未找到返回 None。仅更新传入的非空字段；
    若更新包含 sku / category_id / unit_id，分别校验唯一性与外键存在性。"""
    db_product = get_product(db, product_id)
    if db_product is None:
        return None
    update_data = product.model_dump(exclude_unset=True)
    # sku 唯一性校验（排除自身）
    if "sku" in update_data and update_data["sku"] is not None:
        existing = db.execute(
            select(Product).where(
                Product.sku == update_data["sku"],
                Product.id != product_id,
                Product.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="商品编码已存在",
            )
    # category_id 外键校验（可空）
    if "category_id" in update_data and update_data["category_id"] is not None:
        category = db.execute(
            select(Category).where(
                Category.id == update_data["category_id"],
                Category.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="分类不存在或已删除",
            )
    # unit_id 外键校验
    if "unit_id" in update_data and update_data["unit_id"] is not None:
        unit = db.execute(
            select(Unit).where(
                Unit.id == update_data["unit_id"],
                Unit.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if unit is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="计量单位不存在或已删除",
            )
    for field, value in update_data.items():
        setattr(db_product, field, value)
    db.commit()
    db.refresh(db_product)
    return db_product


def delete_product(db: Session, product_id: int) -> bool:
    """逻辑删除商品（is_deleted=1），未找到返回 False。"""
    db_product = get_product(db, product_id)
    if db_product is None:
        return False
    db_product.is_deleted = 1
    db.commit()
    return True
