"""商品分类 CRUD。

使用 SQLAlchemy 2.x 风格（select() / session.execute()）。
所有查询默认过滤 is_deleted=0；删除为逻辑删除（is_deleted=1），不物理删除。
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.category import Category
from schemas.category import CategoryCreate, CategoryUpdate


def get_category(db: Session, category_id: int) -> Category | None:
    """根据 ID 查询单个未删除分类。"""
    stmt = select(Category).where(
        Category.id == category_id,
        Category.is_deleted == 0,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_categories(db: Session, skip: int = 0, limit: int = 100) -> list[Category]:
    """分页查询未删除分类列表，按 sort 升序、id 升序排序。"""
    stmt = (
        select(Category)
        .where(Category.is_deleted == 0)
        .order_by(Category.sort.asc(), Category.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


def create_category(db: Session, category: CategoryCreate) -> Category:
    """新增分类。若指定 parent_id，校验父分类存在且未删除。"""
    if category.parent_id is not None:
        parent = db.execute(
            select(Category).where(
                Category.id == category.parent_id,
                Category.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父分类不存在或已删除",
            )
    db_category = Category(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_category(
    db: Session, category_id: int, category: CategoryUpdate
) -> Category | None:
    """根据 ID 更新分类，未找到返回 None。仅更新传入的非空字段；
    若本次更新包含非 None 的 parent_id，校验父分类存在且未删除。"""
    db_category = get_category(db, category_id)
    if db_category is None:
        return None
    update_data = category.model_dump(exclude_unset=True)
    if "parent_id" in update_data and update_data["parent_id"] is not None:
        parent = db.execute(
            select(Category).where(
                Category.id == update_data["parent_id"],
                Category.is_deleted == 0,
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="父分类不存在或已删除",
            )
    for field, value in update_data.items():
        setattr(db_category, field, value)
    db.commit()
    db.refresh(db_category)
    return db_category


def delete_category(db: Session, category_id: int) -> bool:
    """逻辑删除分类（is_deleted=1），未找到返回 False。"""
    db_category = get_category(db, category_id)
    if db_category is None:
        return False
    db_category.is_deleted = 1
    db.commit()
    return True
