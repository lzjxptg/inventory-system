"""客户门店管理路由。

提供客户门店的增删改查及设默认接口。
复用 customer:view / customer:create 权限码，不新增权限码。
所有端点需登录鉴权（main.py 统一加 PROTECTED）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.permissions import require_permission
from core.response import error, success
from crud.customer_shop import (
    create_customer_shop,
    delete_customer_shop,
    get_customer_shops_by_customer,
    get_shop,
    set_default_shop,
    update_customer_shop,
)
from schemas.customer_shop import (
    CustomerShopCreate,
    CustomerShopOut,
    CustomerShopUpdate,
)

router = APIRouter(prefix="/api/v1/customer-shops", tags=["客户门店"])


@router.post("", dependencies=[Depends(require_permission("customer:create"))])
def create_shop_api(
    shop: CustomerShopCreate,
    db: Session = Depends(get_db),
):
    """新增客户门店。"""
    item = create_customer_shop(db, shop)
    return success(
        data=CustomerShopOut.model_validate(item).model_dump(),
        msg="创建门店成功",
    )


@router.get("", dependencies=[Depends(require_permission("customer:view"))])
def list_shops_api(
    customer_id: int = Query(..., description="按客户ID筛选"),
    db: Session = Depends(get_db),
):
    """查询指定客户下的门店列表。"""
    items = get_customer_shops_by_customer(db, customer_id)
    return success(
        data=[CustomerShopOut.model_validate(item).model_dump() for item in items]
    )


@router.get("/{shop_id}", dependencies=[Depends(require_permission("customer:view"))])
def get_shop_api(shop_id: int, db: Session = Depends(get_db)):
    """查询门店详情。"""
    item = get_shop(db, shop_id)
    if item is None:
        return error(code=404, msg="门店不存在")
    return success(data=CustomerShopOut.model_validate(item).model_dump())


@router.put("/{shop_id}", dependencies=[Depends(require_permission("customer:create"))])
def update_shop_api(
    shop_id: int,
    shop: CustomerShopUpdate,
    db: Session = Depends(get_db),
):
    """编辑门店。"""
    item = update_customer_shop(db, shop_id, shop)
    if item is None:
        return error(code=404, msg="门店不存在")
    return success(
        data=CustomerShopOut.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/{shop_id}", dependencies=[Depends(require_permission("customer:create"))])
def delete_shop_api(shop_id: int, db: Session = Depends(get_db)):
    """逻辑删除门店。"""
    ok = delete_customer_shop(db, shop_id)
    if not ok:
        return error(code=404, msg="门店不存在")
    return success(msg="删除成功")


@router.post("/{shop_id}/set-default", dependencies=[Depends(require_permission("customer:create"))])
def set_default_api(shop_id: int, db: Session = Depends(get_db)):
    """设为默认门店（同客户其他门店自动取消默认）。"""
    item = set_default_shop(db, shop_id)
    if item is None:
        return error(code=404, msg="门店不存在")
    return success(
        data=CustomerShopOut.model_validate(item).model_dump(),
        msg="已设为默认门店",
    )
