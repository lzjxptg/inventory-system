"""ORM 模型聚合入口。

集中导入全部模型类，确保 ``import models`` 时所有表注册到 ``Base.metadata``。
建表脚本（``Base.metadata.create_all``）只需 ``import models`` 即可覆盖全部表。
"""

from .category import Category
from .customer import Customer
from .inventory import InventoryBalance, StockMovement
from .product import Product
from .role import Permission, Role, RolePermission
from .purchase import PurchaseIn, PurchaseInItem, PurchaseOrder, PurchaseOrderItem
from .purchase_return import PurchaseReturn, PurchaseReturnItem
from .sale_return import SalesReturn, SalesReturnItem
from .sales import SalesOrder, SalesOrderItem, SalesOut, SalesOutItem
from .supplier import Supplier
from .unit import Unit
from .user import User
from .warehouse import Warehouse

__all__ = [
    "Category",
    "Customer",
    "InventoryBalance",
    "Permission",
    "Product",
    "PurchaseIn",
    "PurchaseInItem",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseReturn",
    "PurchaseReturnItem",
    "Role",
    "RolePermission",
    "SalesOrder",
    "SalesOrderItem",
    "SalesOut",
    "SalesOutItem",
    "SalesReturn",
    "SalesReturnItem",
    "StockMovement",
    "Supplier",
    "Unit",
    "User",
    "Warehouse",
]
