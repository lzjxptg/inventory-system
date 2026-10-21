# 14. 客户门店子表设计（SDD）

版本：v1.0
日期：2026-10-22
模块：客户门店 / 销售订单收货门店联动

## 14.1 模块概述

### 14.1.1 背景

- 系统现有 `customers` 表仅支持单条收货地址（`address` 字段），无法满足连锁客户存在多个收货门店的场景。
- 销售订单需指定具体送货门店与地址，原 `customer.address` 粒度不足。
- 本模块采用**子表方案（方案二）**：新增 `customer_shops` 子表，一个客户可拥有多个门店；`sales_orders` 新增 `shop_id` 外键关联具体门店。

### 14.1.2 设计决策

- **方案选择**：子表方案优于在 `customers` 上加 JSON 门店字段，原因是门店需独立增删改查、设默认、参与订单关联与统计。
- **逻辑删除 + 唯一约束**：唯一约束 `(customer_id, shop_name, is_deleted)`，保证同一客户下未删除的门店名不重复，删除后可重建同名门店。
- **外键策略**：`customer_shops.customer_id` → `customers.id` 使用 `CASCADE`，客户删除时其门店级联删除；`sales_orders.shop_id` → `customer_shops.id` 使用 `SET NULL`，门店删除后订单保留但门店置空。

### 14.1.3 涉及的表

| 表名 | 说明 | 变更类型 |
|------|------|---------|
| `customer_shops` | 客户收货门店子表 | 新建 |
| `sales_orders` | 销售订单头，新增 `shop_id` | 加字段 + 索引 + 外键 |

通过 Alembic migration `c3d4e5f6a7b8_add_customer_shops_and_sales_order_shop_id.py` 一次性创建（`down_revision = b2c3d4e5f6a7`）。

## 14.2 数据库设计

### 14.2.1 customer_shops

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | int | PK, AUTO_INCREMENT | 主键 |
| `customer_id` | int | NOT NULL, FK → customers.id (CASCADE), INDEX | 所属客户 |
| `shop_name` | varchar(100) | NOT NULL | 门店名称 |
| `contact` | varchar(50) | NULLABLE | 联系人 |
| `phone` | varchar(20) | NULLABLE | 电话 |
| `address` | varchar(200) | NULLABLE | 收货地址 |
| `is_default` | tinyint(1) | DEFAULT 0 | 是否默认门店 |
| `is_deleted` | tinyint(1) | DEFAULT 0 | 逻辑删除 |
| `created_at` | datetime | DEFAULT now() | 创建时间 |
| `updated_at` | datetime | DEFAULT now(), onupdate now() | 更新时间 |

**唯一约束**：`uq_cs_customer_shop_name (customer_id, shop_name, is_deleted)`

**索引**：`ix_customer_shops_customer_id (customer_id)`

### 14.2.2 sales_orders 新增字段

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `shop_id` | bigint | NULLABLE, FK → customer_shops.id (SET NULL), INDEX | 收货门店，NULL 表示不指定 |

**索引**：`ix_sales_orders_shop_id (shop_id)`

## 14.3 后端实现

### 14.3.1 Model

- `models/customer_shop.py`：`CustomerShop` 模型，含 `customer` relationship。
- `models/sales.py`：`SalesOrder` 新增 `shop_id` 字段、`shop` relationship、`shop_name` / `shop_address` property。
- `models/__init__.py`：导出 `CustomerShop`。

### 14.3.2 Schema

- `schemas/customer_shop.py`：`CustomerShopCreate`、`CustomerShopUpdate`、`CustomerShopOut`。
- `schemas/sales.py`：`SalesOrderCreate`/`SalesOrderUpdate` 新增 `shop_id: int | None = None`；`SalesOrderResponse` 新增 `shop_id`、`shop_name`、`shop_address`。

### 14.3.3 CRUD

- `crud/customer_shop.py`：
  - `create_customer_shop`：校验客户存在、门店名不重复；若 `is_default=1`，同客户其他门店置 0。
  - `get_customer_shops_by_customer`：按客户查询，默认门店 `is_default desc` 排序在前。
  - `get_shop` / `update_customer_shop` / `delete_customer_shop`（逻辑删除）。
  - `set_default_shop`：将目标门店设默认，同客户其他门店 `is_default=0`。
- `crud/sales.py`：
  - `_check_shop_belongs_to_customer`：若 `shop_id` 非空，校验门店属于所选客户且未删除，否则抛 `ValidationException("收货门店不存在或不属于该客户")`。
  - `get_order` / `list_orders`：`joinedload(SalesOrder.shop)` 加载门店关系。
  - `create_order` / `update_order`：调用校验并写入 `shop_id`。

### 14.3.4 Router

- `routers/customer_shops.py`，6 个端点：

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | `/api/v1/customer-shops` | `customer:create` | 创建门店 |
| GET | `/api/v1/customer-shops` | `customer:view` | 列表（按 `customer_id` 筛选） |
| GET | `/api/v1/customer-shops/{id}` | `customer:view` | 详情 |
| PUT | `/api/v1/customer-shops/{id}` | `customer:create` | 编辑 |
| DELETE | `/api/v1/customer-shops/{id}` | `customer:create` | 删除 |
| POST | `/api/v1/customer-shops/{id}/set-default` | `customer:create` | 设为默认 |

- `main.py` 注册路由：`app.include_router(customer_shops.router, dependencies=PROTECTED)`。

### 14.3.5 权限

- 复用 `customer:view` / `customer:create` 权限码，不新增门店专属权限码。
- `scripts/seed_roles.py` 补充 `customer:view`、`customer:create` 权限，admin 全量、operator 含 view + create。

## 14.4 前端实现

### 14.4.1 类型与 API

- `types/index.ts`：新增 `CustomerShop`、`CustomerShopCreate`、`CustomerShopUpdate`；`SalesOrder` 新增 `shop_id`、`shop_name`、`shop_address`；`SalesOrderCreate` 新增 `shop_id?`。
- `api/customerShop.ts`：`createCustomerShop`、`getCustomerShops`、`updateCustomerShop`、`deleteCustomerShop`、`setDefaultShop`。
- `api/sales.ts`：创建/编辑订单参数透传 `shop_id`（类型已包含）。

### 14.4.2 页面

- **客户列表页** `views/customer/CustomerList.vue`：操作列新增「门店」按钮，弹窗管理该客户下门店（新增/编辑/删除/设默认）。
- **销售订单创建页** `views/sales/SalesCreate.vue`：选客户后自动加载其门店下拉；门店可选（不选则 `shop_id=null`），默认选中该客户默认门店；选门店后展示门店收货地址。
- **销售订单编辑页** `views/sales/SalesEdit.vue`：同创建页，加载订单时回显 `shop_id` 并加载对应客户门店列表。
- **销售订单列表页** `views/sales/SalesOrders.vue`：详情弹窗显示「送货门店」与「门店地址」。

## 14.5 测试

`tests/test_customer_shops.py` 覆盖 8 个用例：

1. 正常创建门店
2. 同客户门店名重复（40001）
3. 客户不存在（40401）
4. 列表按客户筛选
5. 设默认门店（同客户其他门店 is_default 置 0）
6. 删除门店（列表不再出现）
7. 销售订单传 `shop_id` 创建，详情返回 `shop_name`
8. `shop_id` 不属于所选客户（40001）

全量 pytest 结果：**165 passed**。

## 14.6 错误码速查

| 错误码 | 场景 |
|--------|------|
| 40001 | 同客户门店名重复 / shop_id 不属于所选客户 |
| 40401 | 门店不存在 / 客户不存在 |
