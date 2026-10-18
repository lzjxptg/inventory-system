"""商品管理路由。

提供商品的增删改查接口，响应统一用 success()/error() 包装。
sku 唯一性与 category_id / unit_id 外键校验由 crud 层负责。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.response import error, success
from crud.product import (
    create_product,
    delete_product,
    get_product,
    get_products,
    update_product,
)
from schemas.product import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter(prefix="/api/v1/products", tags=["商品管理"])


@router.get("")
def list_products(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """分页查询未删除商品列表。"""
    items = get_products(db, skip=skip, limit=limit)
    return success(
        data=[ProductResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/{product_id}")
def read_product(product_id: int, db: Session = Depends(get_db)):
    """根据 ID 查询单个商品详情。"""
    item = get_product(db, product_id)
    if item is None:
        return error(code=404, msg="商品不存在")
    return success(data=ProductResponse.model_validate(item).model_dump())


@router.post("")
def create_product_api(product: ProductCreate, db: Session = Depends(get_db)):
    """新增商品（sku 唯一性与外键校验由 crud 层处理）。"""
    item = create_product(db, product)
    return success(
        data=ProductResponse.model_validate(item).model_dump(),
        msg="创建成功",
    )


@router.put("/{product_id}")
def update_product_api(
    product_id: int, product: ProductUpdate, db: Session = Depends(get_db)
):
    """根据 ID 更新商品。"""
    item = update_product(db, product_id, product)
    if item is None:
        return error(code=404, msg="商品不存在")
    return success(
        data=ProductResponse.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/{product_id}")
def delete_product_api(product_id: int, db: Session = Depends(get_db)):
    """根据 ID 逻辑删除商品。"""
    ok = delete_product(db, product_id)
    if not ok:
        return error(code=404, msg="商品不存在")
    return success(msg="删除成功")
