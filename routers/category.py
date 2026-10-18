"""分类管理路由。

提供分类的增删改查及树形结构接口，响应统一用 success()/error() 包装。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.response import error, success
from crud.category import (
    create_category,
    delete_category,
    get_categories,
    get_category,
    update_category,
)
from models.category import Category
from schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryTreeNode,
    CategoryUpdate,
)

router = APIRouter(prefix="/api/v1/categories", tags=["分类管理"])


def _build_category_tree(db: Session) -> list[CategoryTreeNode]:
    """查询全部未删除分类并构建父子嵌套的树形结构。"""
    items = db.execute(
        select(Category).where(Category.is_deleted == 0)
    ).scalars().all()
    # id -> ORM 对象
    node_map: dict[int, Category] = {item.id: item for item in items}
    # parent_id -> 子节点 id 列表
    children_map: dict[int | None, list[int]] = {}
    for item in items:
        children_map.setdefault(item.parent_id, []).append(item.id)

    def build(parent_id: int | None) -> list[CategoryTreeNode]:
        nodes: list[CategoryTreeNode] = []
        for child_id in children_map.get(parent_id, []):
            item = node_map[child_id]
            node = CategoryTreeNode(
                id=item.id,
                name=item.name,
                parent_id=item.parent_id,
                sort=item.sort,
                children=build(item.id),
            )
            nodes.append(node)
        return nodes

    return build(None)


@router.get("")
def list_categories(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    """分页查询未删除分类列表。"""
    items = get_categories(db, skip=skip, limit=limit)
    return success(
        data=[CategoryResponse.model_validate(item).model_dump() for item in items]
    )


@router.get("/tree")
def get_category_tree(db: Session = Depends(get_db)):
    """查询分类树形结构（嵌套父子关系）。"""
    tree_nodes = _build_category_tree(db)
    return success(data=[node.model_dump() for node in tree_nodes])


@router.get("/{category_id}")
def read_category(category_id: int, db: Session = Depends(get_db)):
    """根据 ID 查询单个分类详情。"""
    item = get_category(db, category_id)
    if item is None:
        return error(code=404, msg="分类不存在")
    return success(data=CategoryResponse.model_validate(item).model_dump())


@router.post("")
def create_category_api(
    category: CategoryCreate, db: Session = Depends(get_db)
):
    """新增分类。"""
    item = create_category(db, category)
    return success(
        data=CategoryResponse.model_validate(item).model_dump(),
        msg="创建成功",
    )


@router.put("/{category_id}")
def update_category_api(
    category_id: int, category: CategoryUpdate, db: Session = Depends(get_db)
):
    """根据 ID 更新分类。"""
    item = update_category(db, category_id, category)
    if item is None:
        return error(code=404, msg="分类不存在")
    return success(
        data=CategoryResponse.model_validate(item).model_dump(),
        msg="更新成功",
    )


@router.delete("/{category_id}")
def delete_category_api(category_id: int, db: Session = Depends(get_db)):
    """根据 ID 逻辑删除分类。"""
    ok = delete_category(db, category_id)
    if not ok:
        return error(code=404, msg="分类不存在")
    return success(msg="删除成功")
