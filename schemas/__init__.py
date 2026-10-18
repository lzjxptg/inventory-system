"""Pydantic Schema 聚合入口。

集中导出基础档案模块全部 Schema，供 routers/crud 层引用。
``_BaseSchema`` 为内部基类，仅提供 ``from_attributes`` 配置，
不对外导出（不放入 ``__all__``）。各模块 Response 类即使继承了
``_BaseSchema`` 也会显式重写 ``model_config``，方便单独调整。
"""

from pydantic import BaseModel, ConfigDict


class _BaseSchema(BaseModel):
    """内部基类：开启 ORM 对象属性读取。"""

    model_config = ConfigDict(from_attributes=True)


from .category import (  # noqa: E402
    CategoryCreate,
    CategoryResponse,
    CategoryTreeNode,
    CategoryUpdate,
)
from .unit import UnitCreate, UnitResponse, UnitUpdate  # noqa: E402
from .product import ProductCreate, ProductResponse, ProductUpdate  # noqa: E402
from .supplier import SupplierCreate, SupplierResponse, SupplierUpdate  # noqa: E402
from .customer import CustomerCreate, CustomerResponse, CustomerUpdate  # noqa: E402
from .warehouse import WarehouseCreate, WarehouseResponse, WarehouseUpdate  # noqa: E402
from .user import Token, UserCreate, UserOut  # noqa: E402
from .inventory import (  # noqa: E402
    InventoryAdjustRequest,
    InventoryBalanceOut,
    StockMovementCreate,
    StockMovementOut,
)
from .purchase import (  # noqa: E402
    PurchaseInCreate,
    PurchaseInItemCreate,
    PurchaseInItemOut,
    PurchaseInResponse,
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    PurchaseOrderItemOut,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)
from .sales import (  # noqa: E402
    SalesOutCreate,
    SalesOutItemCreate,
    SalesOutItemOut,
    SalesOutResponse,
    SalesOrderCreate,
    SalesOrderItemCreate,
    SalesOrderItemOut,
    SalesOrderResponse,
    SalesOrderUpdate,
)

__all__ = [
    # category
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryResponse",
    "CategoryTreeNode",
    # unit
    "UnitCreate",
    "UnitUpdate",
    "UnitResponse",
    # product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    # supplier
    "SupplierCreate",
    "SupplierUpdate",
    "SupplierResponse",
    # customer
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    # warehouse
    "WarehouseCreate",
    "WarehouseUpdate",
    "WarehouseResponse",
    # user / auth
    "UserCreate",
    "UserOut",
    "Token",
    # inventory
    "StockMovementCreate",
    "StockMovementOut",
    "InventoryBalanceOut",
    "InventoryAdjustRequest",
    # purchase
    "PurchaseOrderCreate",
    "PurchaseOrderUpdate",
    "PurchaseOrderResponse",
    "PurchaseOrderItemCreate",
    "PurchaseOrderItemOut",
    "PurchaseInCreate",
    "PurchaseInItemCreate",
    "PurchaseInItemOut",
    "PurchaseInResponse",
    # sales
    "SalesOrderCreate",
    "SalesOrderUpdate",
    "SalesOrderResponse",
    "SalesOrderItemCreate",
    "SalesOrderItemOut",
    "SalesOutCreate",
    "SalesOutItemCreate",
    "SalesOutItemOut",
    "SalesOutResponse",
]
