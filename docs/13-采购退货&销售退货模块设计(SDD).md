# 13. 采购退货 & 销售退货模块设计（SDD）

版本：v1.0
日期：2026-10-21
模块：采购退货 / 销售退货

## 13.1 模块概述

### 13.1.1 背景

- 采购入库后若发现商品质量、规格不符，需将商品退回供应商并冲减库存；销售出库后客户拒收或退货，需将商品退回仓库并回补库存。
- 系统已有采购订单 / 销售订单链路，但缺少逆向单据（退货单），无法对已入库 / 已出库商品进行反向冲销与库存回滚。
- 本模块新增「采购退货单」与「销售退货单」两类逆向单据，审核通过时联动库存，形成完整的采购 / 销售闭环。

### 13.1.2 与原订单的关系

- 采购退货单通过 `purchase_order_id` 关联原采购订单，供应商、仓库从原订单带出，不可修改。
- 销售退货单通过 `sales_order_id` 关联原销售订单，客户、仓库从原订单带出，不可修改。
- 退货数量不得超过原订单对应商品的「已入库数量」（采购 `received_quantity`）或「已出库数量」（销售 `shipped_quantity`）。
- 允许创建退货单的原订单状态：采购为 `approved / partial_in / received / completed`，销售为 `approved / partial_out / completed`。

### 13.1.3 涉及的表

| 表名 | 说明 |
|------|------|
| `purchase_returns` | 采购退货单头 |
| `purchase_return_items` | 采购退货单明细 |
| `sales_returns` | 销售退货单头 |
| `sales_return_items` | 销售退货单明细 |

通过 Alembic migration `a1b2c3d4e5f6_add_purchase_and_sales_return_tables.py` 一次性创建（`down_revision = 064d6b94f98e`）。

## 13.2 业务流程

### 13.2.1 状态流转

```
        创建
         │
         ▼
      [draft] ───提交───► [submitted] ───审核通过───► [approved]
         │                    │
         │                    └───驳回───► [rejected]
         │
      编辑 / 删除（仅 draft 可操作）
```

- **draft（草稿）**：可修改明细、可删除、可提交。
- **submitted（已提交）**：等待审核，不可修改 / 删除，仅 admin 可审核通过或驳回。
- **approved（已审核）**：审核通过，库存已联动，不可再改。
- **rejected（已驳回）**：审核驳回，终态。

### 13.2.2 库存联动方向

| 单据 | 审核通过后库存动作 | 流水类型 | 数量符号 |
|------|------------------|---------|---------|
| 采购退货 | 商品退回仓库，`inventory_balance` **增加** | `IN` | 正数 |
| 销售退货 | 商品出库退回客户，`inventory_balance` **扣减** | `OUT` | 负数 |

### 13.2.3 退货数量约束

- 采购退货：单商品退货数量 ≤ 原采购订单明细的 `received_quantity`（已入库数量）。
- 销售退货：单商品退货数量 ≤ 原销售订单明细的 `shipped_quantity`（已出库数量）。
- 同一退货单内同一商品不可重复出现（明细唯一约束 `(return_id, product_id)`）。
- 校验不通过返回业务错误码 `40001`（ValidationException）。

## 13.3 数据模型

### 13.3.1 purchase_returns（采购退货单头）

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BigInteger | 主键 ID | PK, autoincrement |
| return_no | VARCHAR(64) | 退货单号，格式 `PR-YYYYMMDD-序号` | NOT NULL, UNIQUE (`uq_purchase_returns_return_no`) |
| purchase_order_id | BigInteger | 关联采购订单 ID | FK → purchase_orders.id (RESTRICT), NOT NULL, INDEX |
| supplier_id | BigInteger | 供应商 ID | FK → suppliers.id (RESTRICT), NOT NULL, INDEX |
| warehouse_id | BigInteger | 退货入库仓库 ID | FK → warehouses.id (RESTRICT), NOT NULL |
| return_date | DATETIME | 退货日期 | NOT NULL, DEFAULT now() |
| total_quantity | DECIMAL(12,2) | 退货总数量 | NOT NULL, DEFAULT 0.00 |
| total_amount | DECIMAL(12,2) | 退货总金额 | NOT NULL, DEFAULT 0.00 |
| status | VARCHAR(20) | 状态：draft / submitted / approved / rejected | NOT NULL, DEFAULT 'draft', INDEX |
| reason | VARCHAR(500) | 退货原因 | NULLABLE |
| created_by | BigInteger | 创建人 ID | FK → users.id (RESTRICT), NOT NULL |
| approved_by | BigInteger | 审核人 ID | FK → users.id (SET NULL), NULLABLE |
| approved_at | DATETIME | 审核时间 | NULLABLE |
| updated_at | DATETIME | 更新时间 | NOT NULL, DEFAULT now(), onupdate now() |
| is_deleted | TINYINT | 逻辑删除：0 正常 / 1 已删除 | NOT NULL, DEFAULT 0 |
| created_at | DATETIME | 创建时间 | NOT NULL, DEFAULT now() |

索引：`ix_purchase_returns_order_id`、`ix_purchase_returns_status`、`ix_purchase_returns_supplier_id`。

### 13.3.2 purchase_return_items（采购退货明细）

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BigInteger | 主键 ID | PK, autoincrement |
| return_id | BigInteger | 采购退货单 ID | FK → purchase_returns.id (CASCADE), NOT NULL, INDEX |
| product_id | BigInteger | 商品 ID | FK → products.id (RESTRICT), NOT NULL, INDEX |
| quantity | DECIMAL(12,2) | 退货数量 | NOT NULL |
| unit_price | DECIMAL(12,2) | 退货单价 | NOT NULL |
| amount | DECIMAL(12,2) | 金额 = 数量 × 单价 | NOT NULL |
| batch_no | VARCHAR(64) | 批次号 | NULLABLE |
| is_deleted | TINYINT | 逻辑删除 | NOT NULL, DEFAULT 0 |
| created_at | DATETIME | 创建时间 | NOT NULL, DEFAULT now() |

唯一约束：`uq_pri_return_product (return_id, product_id)`。

### 13.3.3 sales_returns（销售退货单头）

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BigInteger | 主键 ID | PK, autoincrement |
| return_no | VARCHAR(64) | 退货单号，格式 `SR-YYYYMMDD-序号` | NOT NULL, UNIQUE (`uq_sales_returns_return_no`) |
| sales_order_id | BigInteger | 关联销售订单 ID | FK → sales_orders.id (RESTRICT), NOT NULL, INDEX |
| customer_id | BigInteger | 客户 ID | FK → customers.id (RESTRICT), NOT NULL, INDEX |
| warehouse_id | BigInteger | 退货出库仓库 ID | FK → warehouses.id (RESTRICT), NOT NULL |
| return_date | DATETIME | 退货日期 | NOT NULL, DEFAULT now() |
| total_quantity | DECIMAL(12,2) | 退货总数量 | NOT NULL, DEFAULT 0.00 |
| total_amount | DECIMAL(12,2) | 退货总金额 | NOT NULL, DEFAULT 0.00 |
| status | VARCHAR(20) | 状态：draft / submitted / approved / rejected | NOT NULL, DEFAULT 'draft', INDEX |
| reason | VARCHAR(500) | 退货原因 | NULLABLE |
| created_by | BigInteger | 创建人 ID | FK → users.id (RESTRICT), NOT NULL |
| approved_by | BigInteger | 审核人 ID | FK → users.id (SET NULL), NULLABLE |
| approved_at | DATETIME | 审核时间 | NULLABLE |
| updated_at | DATETIME | 更新时间 | NOT NULL, DEFAULT now(), onupdate now() |
| is_deleted | TINYINT | 逻辑删除 | NOT NULL, DEFAULT 0 |
| created_at | DATETIME | 创建时间 | NOT NULL, DEFAULT now() |

索引：`ix_sales_returns_order_id`、`ix_sales_returns_status`、`ix_sales_returns_customer_id`。

### 13.3.4 sales_return_items（销售退货明细）

| 字段 | 类型 | 说明 | 约束 |
|------|------|------|------|
| id | BigInteger | 主键 ID | PK, autoincrement |
| return_id | BigInteger | 销售退货单 ID | FK → sales_returns.id (CASCADE), NOT NULL, INDEX |
| product_id | BigInteger | 商品 ID | FK → products.id (RESTRICT), NOT NULL, INDEX |
| quantity | DECIMAL(12,2) | 退货数量 | NOT NULL |
| unit_price | DECIMAL(12,2) | 退货单价 | NOT NULL |
| amount | DECIMAL(12,2) | 金额 = 数量 × 单价 | NOT NULL |
| batch_no | VARCHAR(64) | 批次号 | NULLABLE |
| is_deleted | TINYINT | 逻辑删除 | NOT NULL, DEFAULT 0 |
| created_at | DATETIME | 创建时间 | NOT NULL, DEFAULT now() |

唯一约束：`uq_sri_return_product (return_id, product_id)`。

## 13.4 接口清单

所有接口基础路径 `/api/v1`，均需登录鉴权（`main.py` 统一注入 `PROTECTED`）。

### 13.4.1 采购退货（8 个）

| 方法 | 路径 | 说明 | 权限码 | 调用方 |
|------|------|------|--------|--------|
| POST | /api/v1/purchase-returns | 创建退货单（草稿） | `purchase_return:create` | 前端 |
| GET | /api/v1/purchase-returns | 列表（分页 + 按 status / supplier_id / keyword 筛选） | `purchase_return:view`（导出用）/ 列表仅登录 | 前端 |
| GET | /api/v1/purchase-returns/export | 导出 Excel | `purchase_return:view` | 前端 |
| GET | /api/v1/purchase-returns/{return_id} | 详情（含明细） | 仅登录 | 前端 |
| PUT | /api/v1/purchase-returns/{return_id} | 修改退货单（仅 draft，明细全量替换） | 仅登录 | 前端 |
| DELETE | /api/v1/purchase-returns/{return_id} | 删除退货单（仅 draft，逻辑删除） | 仅登录 | 前端 |
| POST | /api/v1/purchase-returns/{return_id}/submit | 提交审核（draft → submitted） | 仅登录 | 前端 |
| POST | /api/v1/purchase-returns/{return_id}/approve | 审核通过（联动库存 IN） | `purchase_return:approve` | 前端 |
| POST | /api/v1/purchase-returns/{return_id}/reject | 驳回（submitted → rejected） | 仅登录 | 前端 |

### 13.4.2 销售退货（8 个）

| 方法 | 路径 | 说明 | 权限码 | 调用方 |
|------|------|------|--------|--------|
| POST | /api/v1/sales-returns | 创建退货单（草稿） | `sales_return:create` | 前端 |
| GET | /api/v1/sales-returns | 列表（分页 + 按 status / customer_id / keyword 筛选） | `sales_return:view`（导出用）/ 列表仅登录 | 前端 |
| GET | /api/v1/sales-returns/export | 导出 Excel | `sales_return:view` | 前端 |
| GET | /api/v1/sales-returns/{return_id} | 详情（含明细） | 仅登录 | 前端 |
| PUT | /api/v1/sales-returns/{return_id} | 修改退货单（仅 draft，明细全量替换） | 仅登录 | 前端 |
| DELETE | /api/v1/sales-returns/{return_id} | 删除退货单（仅 draft，逻辑删除） | 仅登录 | 前端 |
| POST | /api/v1/sales-returns/{return_id}/submit | 提交审核（draft → submitted） | 仅登录 | 前端 |
| POST | /api/v1/sales-returns/{return_id}/approve | 审核通过（联动库存 OUT） | `sales_return:approve` | 前端 |
| POST | /api/v1/sales-returns/{return_id}/reject | 驳回（submitted → rejected） | 仅登录 | 前端 |

> 注：采购、销售各 9 行（含详情），其中 create / approve / export 三类接口带权限码校验，其余仅要求登录。

## 13.5 权限矩阵

新增 6 个权限码：`purchase_return:view`、`purchase_return:create`、`purchase_return:approve`、`sales_return:view`、`sales_return:create`、`sales_return:approve`（系统权限码总数由 12 增至 18）。

| 操作 | admin | operator |
|------|-------|----------|
| 查看退货单 / 列表 / 详情 / 导出 | ✅ | ✅ |
| 创建退货单 | ✅ | ✅ |
| 修改 / 删除草稿退货单 | ✅ | ✅ |
| 提交审核 | ✅ | ✅ |
| 审核通过 / 驳回 | ✅ | ❌ |

admin 角色拥有全部 18 项权限；operator 角色拥有退货的 view / create（不含 approve）。

## 13.6 库存联动逻辑

审核通过（approve）时，在同一数据库事务内完成「校验 → 写流水 → 改状态 → 提交」。

### 13.6.1 采购退货（IN 入库）

- 前置校验：退货单状态必须为 `submitted`，否则抛 `ConflictException`（40901）。
- 对每条明细构造 `StockMovementCreate`：
  - `movement_type = "IN"`
  - `quantity = item.quantity`（正数）
  - `reference_type = "PURCHASE_RETURN"`，`reference_id = return.id`
- 调用 `crud.inventory.create_stock_movements(db, movements, approved_by)` 批量写入流水（内部只 `flush`，不 `commit`），由其更新 `inventory_balance.current_quantity`。
- 更新退货单：`status = "approved"`、`approved_by`、`approved_at = now()`。
- 统一 `db.commit()` 提交事务。

### 13.6.2 销售退货（OUT 出库）

- 前置校验同上（状态为 `submitted`）。
- 对每条明细构造 `StockMovementCreate`：
  - `movement_type = "OUT"`
  - `quantity = -abs(item.quantity)`（负数）
  - `reference_type = "SALES_RETURN"`，`reference_id = return.id`
- `create_stock_movements` 内部对出库（quantity < 0）校验库存充足，不足则抛 `ValidationException`（40001）并回滚。
- 更新退货单状态为 `approved`，统一 `commit`。

### 13.6.3 事务保证

- 流水写入与状态变更在同一事务中，任一步失败整体回滚，避免「库存变了但单据没审核」或反之。
- `create_stock_movements` 只负责 flush，commit 权交还给退货模块的 approve 函数。

## 13.7 测试覆盖

退货模块新增 5 个 pytest 用例（`tests/test_returns.py`），全量测试 **157 passed**。

| 用例 | 验证点 |
|------|--------|
| `test_purchase_return_create_and_approve_increases_stock` | 创建采购退货单 → 提交 → 审核通过；验证库存由 100 增至 130，且存在 `reference_type=PURCHASE_RETURN` 的 IN 流水（quantity=30） |
| `test_purchase_return_quantity_exceeds_received` | 退货数量超过已入库数量时返回 `code=40001` |
| `test_purchase_return_delete_draft_only` | 已提交的退货单删除失败（非草稿不可删） |
| `test_purchase_return_list` | 列表接口正常返回数组 |
| `test_sales_return_approve_decreases_stock` | 销售退货审核通过后库存由 50 扣减至 20，且存在 `reference_type=SALES_RETURN` 的 OUT 流水（quantity=-30） |

## 13.8 前端页面

### 13.8.1 页面文件

| 文件 | 功能 |
|------|------|
| `frontend/src/views/purchase-return/PurchaseReturnList.vue` | 采购退货列表（筛选 + 分页 + 导出 + 新建跳转 + 行内提交 / 审核 / 驳回 / 删除） |
| `frontend/src/views/purchase-return/PurchaseReturnCreate.vue` | 新建 / 编辑采购退货单（选原订单 → 自动带出供应商仓库 → 明细表填写退货数量，max=已入库数量 → 实时计算总额） |
| `frontend/src/views/purchase-return/PurchaseReturnDetail.vue` | 采购退货详情 + 审核操作 |
| `frontend/src/views/sales-return/SalesReturnList.vue` | 销售退货列表（对称） |
| `frontend/src/views/sales-return/SalesReturnCreate.vue` | 新建 / 编辑销售退货单（max=已出库数量） |
| `frontend/src/views/sales-return/SalesReturnDetail.vue` | 销售退货详情 + 审核操作 |

### 13.8.2 路由配置（8 条）

| 路径 | 页面 |
|------|------|
| `/purchase-returns` | PurchaseReturnList |
| `/purchase-returns/create` | PurchaseReturnCreate |
| `/purchase-returns/edit/:id` | PurchaseReturnCreate（编辑） |
| `/purchase-returns/:id` | PurchaseReturnDetail |
| `/sales-returns` | SalesReturnList |
| `/sales-returns/create` | SalesReturnCreate |
| `/sales-returns/edit/:id` | SalesReturnCreate（编辑） |
| `/sales-returns/:id` | SalesReturnDetail |

### 13.8.3 菜单位置

- 采购管理子菜单下追加「采购退货」（`/purchase-returns`）。
- 销售管理子菜单下追加「销售退货」（`/sales-returns`）。
- 审核 / 驳回按钮仅 `admin` 角色可见（`authStore.hasRole(['admin'])`）。
- 编辑 / 删除按钮仅 `draft` 状态可见。
