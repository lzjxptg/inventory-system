# API 接口清单

> 本清单基于项目实际代码整理，覆盖全部已注册路由。
> 基础路径：`http://localhost:8002`

## 统一约定

### 鉴权方式

除「认证」模块外，所有业务接口均需在请求头携带 JWT：

```
Authorization: Bearer <access_token>
```

JWT 通过 `POST /api/v1/auth/login` 获取，有效期 30 分钟。

### 响应格式

业务接口统一返回 JSON 包装：

```json
{
  "code": 0,
  "msg": "ok",
  "data": {}
}
```

- `code = 0` 表示成功；非 0 为业务错误码。
- `data` 为业务数据，列表接口返回数组，分页接口返回 `{items, total, page, page_size}`。

登录接口（`/api/v1/auth/login`）例外，直接返回 OAuth2 标准格式：

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

Excel 导出接口返回 `StreamingResponse`，`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`。

### RBAC 权限控制说明

- **登录鉴权**：所有业务接口（除注册/登录外）均要求有效 JWT，由 `main.py` 中 `PROTECTED = [Depends(get_current_user)]` 统一注入。
- **角色校验**：部分管理接口额外要求 `admin` 角色（`require_role("admin")`）。
- **权限码校验**：部分导出接口要求特定权限码（`require_permission("xxx:view")`）。
- 基础档案 CRUD（商品/仓库/分类/单位/供应商/客户）及采购/销售/库存的大部分操作接口仅要求登录，不做细粒度权限码校验。

预置权限码（共 18 项）：

| 权限码 | 名称 | 模块 |
|--------|------|------|
| `role:manage` | 角色管理 | settings |
| `user:role` | 分配用户角色 | settings |
| `purchase:view` | 查看采购 | purchase |
| `purchase:create` | 创建采购 | purchase |
| `purchase:delete` | 删除采购 | purchase |
| `sales:view` | 查看销售 | sales |
| `sales:create` | 创建销售 | sales |
| `sales:delete` | 删除销售 | sales |
| `inventory:view` | 查看库存 | inventory |
| `inventory:in` | 入库操作 | inventory |
| `inventory:out` | 出库操作 | inventory |
| `reports:view` | 查看报表 | reports |
| `purchase_return:view` | 查看采购退货 | purchase_return |
| `purchase_return:create` | 创建采购退货 | purchase_return |
| `purchase_return:approve` | 审核采购退货 | purchase_return |
| `sales_return:view` | 查看销售退货 | sales_return |
| `sales_return:create` | 创建销售退货 | sales_return |
| `sales_return:approve` | 审核销售退货 | sales_return |

admin 角色拥有全部 18 项；operator 角色拥有 14 项（不含 `:delete`、`role:manage`、`user:role` 及各类 `:approve`）。

---

## 1. 认证模块（/api/v1/auth）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/auth/register` | 否 | 无 | Body: `username`, `password`, `phone?` | `success(data=UserOut)` |
| POST | `/api/v1/auth/login` | 否 | 无 | Form: `username`, `password`（OAuth2 表单） | `{access_token, token_type}` |

---

## 2. 用户与角色权限模块（/api/v1）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/roles` | 是 | 无 | Query: `skip`, `limit` | 角色列表 |
| POST | `/api/v1/roles` | 是 | admin | Body: `name`, `description` | 新建角色 |
| PUT | `/api/v1/roles/{role_id}` | 是 | admin | Body: `name?`, `description?` | 更新角色 |
| DELETE | `/api/v1/roles/{role_id}` | 是 | admin | Path: `role_id` | 逻辑删除角色 |
| GET | `/api/v1/permissions` | 是 | 无 | - | 全部权限列表 |
| GET | `/api/v1/roles/me` | 是 | 无 | - | 当前用户信息（含 role） |
| GET | `/api/v1/roles/me/permissions` | 是 | 无 | - | 当前用户权限码列表 |
| GET | `/api/v1/roles/{role_id}/permissions` | 是 | 无 | Path: `role_id` | 角色已分配权限 ID 列表 |
| PUT | `/api/v1/roles/{role_id}/permissions` | 是 | admin | Body: `permission_ids: int[]` | 分配角色权限（全量覆盖） |
| PUT | `/api/v1/users/{user_id}/role` | 是 | admin | Body: `role_id` | 分配用户角色 |
| GET | `/api/v1/users` | 是 | 无 | Query: `skip`, `limit` | 用户列表 |

---

## 3. 商品管理（/api/v1/products）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/products` | 是 | 无 | Query: `skip`, `limit` | 商品列表 |
| GET | `/api/v1/products/{product_id}` | 是 | 无 | Path: `product_id` | 商品详情 |
| POST | `/api/v1/products` | 是 | 无 | Body: `sku`, `name`, `category_id`, `unit_id`, `price?`, `min_stock?` 等 | 新建商品 |
| PUT | `/api/v1/products/{product_id}` | 是 | 无 | Body: 同创建（均可选） | 更新商品 |
| DELETE | `/api/v1/products/{product_id}` | 是 | 无 | Path: `product_id` | 逻辑删除商品 |

---

## 4. 仓库管理（/api/v1/warehouses）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/warehouses` | 是 | 无 | Query: `skip`, `limit` | 仓库列表 |
| GET | `/api/v1/warehouses/{warehouse_id}` | 是 | 无 | Path: `warehouse_id` | 仓库详情 |
| POST | `/api/v1/warehouses` | 是 | 无 | Body: `code`, `name`, `address?` 等 | 新建仓库 |
| PUT | `/api/v1/warehouses/{warehouse_id}` | 是 | 无 | Body: 同创建（均可选） | 更新仓库 |
| DELETE | `/api/v1/warehouses/{warehouse_id}` | 是 | 无 | Path: `warehouse_id` | 逻辑删除仓库 |

---

## 5. 分类管理（/api/v1/categories）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/categories` | 是 | 无 | Query: `skip`, `limit` | 分类列表 |
| GET | `/api/v1/categories/tree` | 是 | 无 | - | 分类树形结构 |
| GET | `/api/v1/categories/{category_id}` | 是 | 无 | Path: `category_id` | 分类详情 |
| POST | `/api/v1/categories` | 是 | 无 | Body: `name`, `parent_id?` | 新建分类 |
| PUT | `/api/v1/categories/{category_id}` | 是 | 无 | Body: `name?`, `parent_id?` | 更新分类 |
| DELETE | `/api/v1/categories/{category_id}` | 是 | 无 | Path: `category_id` | 逻辑删除分类 |

---

## 6. 计量单位（/api/v1/units）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/units` | 是 | 无 | Query: `skip`, `limit` | 单位列表 |
| GET | `/api/v1/units/{unit_id}` | 是 | 无 | Path: `unit_id` | 单位详情 |
| POST | `/api/v1/units` | 是 | 无 | Body: `name` | 新建单位 |
| PUT | `/api/v1/units/{unit_id}` | 是 | 无 | Body: `name` | 更新单位 |
| DELETE | `/api/v1/units/{unit_id}` | 是 | 无 | Path: `unit_id` | 逻辑删除单位 |

---

## 7. 供应商管理（/api/v1/suppliers）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/suppliers` | 是 | 无 | Query: `skip`, `limit` | 供应商列表 |
| GET | `/api/v1/suppliers/{supplier_id}` | 是 | 无 | Path: `supplier_id` | 供应商详情 |
| POST | `/api/v1/suppliers` | 是 | 无 | Body: `name`, `contact?`, `phone?`, `address?` 等 | 新建供应商 |
| PUT | `/api/v1/suppliers/{supplier_id}` | 是 | 无 | Body: 同创建（均可选） | 更新供应商 |
| DELETE | `/api/v1/suppliers/{supplier_id}` | 是 | 无 | Path: `supplier_id` | 逻辑删除供应商 |

---

## 8. 客户管理（/api/v1/customers）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/customers` | 是 | 无 | Query: `skip`, `limit` | 客户列表 |
| GET | `/api/v1/customers/{customer_id}` | 是 | 无 | Path: `customer_id` | 客户详情 |
| POST | `/api/v1/customers` | 是 | 无 | Body: `name`, `contact?`, `phone?`, `address?` 等 | 新建客户 |
| PUT | `/api/v1/customers/{customer_id}` | 是 | 无 | Body: 同创建（均可选） | 更新客户 |
| DELETE | `/api/v1/customers/{customer_id}` | 是 | 无 | Path: `customer_id` | 逻辑删除客户 |

---

## 9. 库存管理（/api/v1/inventory）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/inventory/in` | 是 | 无 | Body: `product_id`, `warehouse_id`, `quantity`, `remark?` | 入库流水 |
| POST | `/api/v1/inventory/out` | 是 | 无 | Body: `product_id`, `warehouse_id`, `quantity`, `remark?` | 出库流水（库存不足返回 400） |
| POST | `/api/v1/inventory/adjust` | 是 | 无 | Body: `product_id`, `warehouse_id`, `new_quantity`, `remark?` | 盘点调整流水 |
| GET | `/api/v1/inventory/balances` | 是 | 无 | Query: `product_id?`, `warehouse_id?`, `skip`, `limit` | 库存余额列表 |
| GET | `/api/v1/inventory/movements` | 是 | 无 | Query: `product_id?`, `warehouse_id?`, `movement_type?`, `skip`, `limit` | 库存流水列表 |
| GET | `/api/v1/inventory/balances/{product_id}/{warehouse_id}` | 是 | 无 | Path: `product_id`, `warehouse_id` | 单商品在单仓库的余额 |
| GET | `/api/v1/inventory/movements/export` | 是 | `inventory:view` | Query: `product_id?`, `warehouse_id?`, `movement_type?`, `format=xlsx` | Excel 文件（库存流水） |

---

## 10. 采购管理（/api/v1/purchases）

### 采购订单

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/purchases/orders` | 是 | 无 | Body: `supplier_id`, `warehouse_id`, `remark?`, `items: [{product_id, quantity, unit_price}]` | 新建采购订单 |
| GET | `/api/v1/purchases/orders` | 是 | 无 | Query: `status?`, `supplier_id?`, `keyword?`, `skip`, `limit` | 采购订单列表 |
| GET | `/api/v1/purchases/orders/export` | 是 | `purchase:view` | Query: `status?`, `supplier_id?`, `keyword?`, `format=xlsx` | Excel 文件（采购订单） |
| GET | `/api/v1/purchases/orders/{order_id}` | 是 | 无 | Path: `order_id` | 采购订单详情（含明细） |
| PUT | `/api/v1/purchases/orders/{order_id}` | 是 | 无 | Body: 同创建（均可选，明细全量替换） | 修改采购订单（仅草稿） |
| POST | `/api/v1/purchases/orders/{order_id}/submit` | 是 | 无 | Path: `order_id` | 提交审核（draft → submitted） |
| POST | `/api/v1/purchases/orders/{order_id}/approve` | 是 | 无 | Path: `order_id` | 审核通过（submitted → approved） |
| POST | `/api/v1/purchases/orders/{order_id}/cancel` | 是 | 无 | Path: `order_id` | 取消订单（已完成不可取消） |
| DELETE | `/api/v1/purchases/orders/{order_id}` | 是 | 无 | Path: `order_id` | 逻辑删除订单（仅草稿） |

### 采购入库单

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/purchases/orders/{order_id}/ins` | 是 | 无 | Path: `order_id`; Body: `items: [{product_id, quantity}]` | 创建采购入库单（草稿） |
| GET | `/api/v1/purchases/ins` | 是 | 无 | Query: `status?`, `purchase_order_id?`, `skip`, `limit` | 入库单列表 |
| GET | `/api/v1/purchases/ins/{in_id}` | 是 | 无 | Path: `in_id` | 入库单详情（含明细） |
| POST | `/api/v1/purchases/ins/{in_id}/confirm` | 是 | 无 | Path: `in_id` | 确认入库（联动库存，核心接口） |
| POST | `/api/v1/purchases/ins/{in_id}/cancel` | 是 | 无 | Path: `in_id` | 取消入库单（仅草稿） |

---

## 11. 销售管理（/api/v1/sales）

### 销售订单

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/sales/orders` | 是 | 无 | Body: `customer_id`, `warehouse_id`, `remark?`, `items: [{product_id, quantity, unit_price}]` | 新建销售订单 |
| GET | `/api/v1/sales/orders` | 是 | 无 | Query: `status?`, `customer_id?`, `keyword?`, `skip`, `limit` | 销售订单列表 |
| GET | `/api/v1/sales/orders/export` | 是 | `sales:view` | Query: `status?`, `customer_id?`, `keyword?`, `format=xlsx` | Excel 文件（销售订单） |
| GET | `/api/v1/sales/orders/{order_id}` | 是 | 无 | Path: `order_id` | 销售订单详情（含明细） |
| PUT | `/api/v1/sales/orders/{order_id}` | 是 | 无 | Body: 同创建（均可选，明细全量替换） | 修改销售订单（仅草稿） |
| POST | `/api/v1/sales/orders/{order_id}/submit` | 是 | 无 | Path: `order_id` | 提交审核（draft → submitted） |
| POST | `/api/v1/sales/orders/{order_id}/approve` | 是 | 无 | Path: `order_id` | 审核通过（submitted → approved） |
| POST | `/api/v1/sales/orders/{order_id}/cancel` | 是 | 无 | Path: `order_id` | 取消订单（已完成不可取消） |
| DELETE | `/api/v1/sales/orders/{order_id}` | 是 | 无 | Path: `order_id` | 逻辑删除订单（仅草稿） |

### 销售出库单

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/sales/orders/{order_id}/outs` | 是 | 无 | Path: `order_id`; Body: `items: [{product_id, quantity}]` | 创建销售出库单（草稿） |
| GET | `/api/v1/sales/outs` | 是 | 无 | Query: `status?`, `sales_order_id?`, `skip`, `limit` | 出库单列表 |
| GET | `/api/v1/sales/outs/{out_id}` | 是 | 无 | Path: `out_id` | 出库单详情（含明细） |
| POST | `/api/v1/sales/outs/{out_id}/confirm` | 是 | 无 | Path: `out_id` | 确认出库（联动库存，核心接口） |
| POST | `/api/v1/sales/outs/{out_id}/cancel` | 是 | 无 | Path: `out_id` | 取消出库单（仅草稿） |

---

## 12. 采购退货（/api/v1/purchase-returns）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/purchase-returns` | 是 | `purchase_return:create` | Body: `purchase_order_id`, `reason?`, `items: [{product_id, quantity, unit_price?, batch_no?}]` | 新建采购退货单（草稿），校验退货数量 ≤ 已入库数量 |
| GET | `/api/v1/purchase-returns` | 是 | 无 | Query: `status?`, `supplier_id?`, `keyword?`, `skip`, `limit` | 采购退货单列表（含明细） |
| GET | `/api/v1/purchase-returns/export` | 是 | `purchase_return:view` | Query: `status?`, `supplier_id?`, `keyword?`, `format=xlsx` | Excel 文件（采购退货单） |
| GET | `/api/v1/purchase-returns/{return_id}` | 是 | 无 | Path: `return_id` | 采购退货单详情（含明细） |
| PUT | `/api/v1/purchase-returns/{return_id}` | 是 | 无 | Path: `return_id`; Body: `reason?`, `items: [...]`（明细全量替换） | 修改退货单（仅 draft） |
| DELETE | `/api/v1/purchase-returns/{return_id}` | 是 | 无 | Path: `return_id` | 逻辑删除退货单（仅 draft） |
| POST | `/api/v1/purchase-returns/{return_id}/submit` | 是 | 无 | Path: `return_id` | 提交审核（draft → submitted） |
| POST | `/api/v1/purchase-returns/{return_id}/approve` | 是 | `purchase_return:approve` | Path: `return_id` | 审核通过（submitted → approved），联动库存 IN 入库 |
| POST | `/api/v1/purchase-returns/{return_id}/reject` | 是 | 无 | Path: `return_id` | 驳回（submitted → rejected） |

创建响应示例：

```json
{
  "code": 0,
  "msg": "创建采购退货单成功",
  "data": {
    "id": 1,
    "return_no": "PR-20261021-0001",
    "purchase_order_id": 10,
    "supplier_id": 1,
    "warehouse_id": 1,
    "status": "draft",
    "total_quantity": 30.0,
    "total_amount": 300.0,
    "reason": "质量问题",
    "items": [
      {"product_id": 5, "quantity": 30.0, "unit_price": 10.0, "amount": 300.0, "batch_no": null}
    ]
  }
}
```

---

## 13. 销售退货（/api/v1/sales-returns）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| POST | `/api/v1/sales-returns` | 是 | `sales_return:create` | Body: `sales_order_id`, `reason?`, `items: [{product_id, quantity, unit_price?, batch_no?}]` | 新建销售退货单（草稿），校验退货数量 ≤ 已出库数量 |
| GET | `/api/v1/sales-returns` | 是 | 无 | Query: `status?`, `customer_id?`, `keyword?`, `skip`, `limit` | 销售退货单列表（含明细） |
| GET | `/api/v1/sales-returns/export` | 是 | `sales_return:view` | Query: `status?`, `customer_id?`, `keyword?`, `format=xlsx` | Excel 文件（销售退货单） |
| GET | `/api/v1/sales-returns/{return_id}` | 是 | 无 | Path: `return_id` | 销售退货单详情（含明细） |
| PUT | `/api/v1/sales-returns/{return_id}` | 是 | 无 | Path: `return_id`; Body: `reason?`, `items: [...]`（明细全量替换） | 修改退货单（仅 draft） |
| DELETE | `/api/v1/sales-returns/{return_id}` | 是 | 无 | Path: `return_id` | 逻辑删除退货单（仅 draft） |
| POST | `/api/v1/sales-returns/{return_id}/submit` | 是 | 无 | Path: `return_id` | 提交审核（draft → submitted） |
| POST | `/api/v1/sales-returns/{return_id}/approve` | 是 | `sales_return:approve` | Path: `return_id` | 审核通过（submitted → approved），联动库存 OUT 出库 |
| POST | `/api/v1/sales-returns/{return_id}/reject` | 是 | 无 | Path: `return_id` | 驳回（submitted → rejected） |

---

## 14. 报表统计（/api/v1/reports）

| 方法 | 路径 | 鉴权 | RBAC | 请求参数 | 响应 |
|------|------|------|------|----------|------|
| GET | `/api/v1/reports/inventory-movements` | 是 | 无 | Query: `product_id?`, `warehouse_id?`, `movement_type?`, `start_date?`, `end_date?`, `page`, `page_size` | 流水汇总（分页） |
| GET | `/api/v1/reports/low-stock-alerts` | 是 | 无 | Query: `warehouse_id?`, `page`, `page_size` | 低库存预警列表（分页） |
| GET | `/api/v1/reports/low-stock-alerts/export` | 是 | `reports:view` | Query: `warehouse_id?`, `format=xlsx` | Excel 文件（低库存预警） |
| GET | `/api/v1/reports/purchase-summary` | 是 | 无 | Query: `start_date`（必填）, `end_date`（必填）, `supplier_id?` | 采购金额统计 |
| GET | `/api/v1/reports/purchase-summary/export` | 是 | `reports:view` | Query: `start_date`（必填）, `end_date`（必填）, `supplier_id?`, `format=xlsx` | Excel 文件（采购统计，双 Sheet） |
| GET | `/api/v1/reports/sales-summary` | 是 | 无 | Query: `start_date`（必填）, `end_date`（必填）, `customer_id?` | 销售金额统计 |
| GET | `/api/v1/reports/sales-summary/export` | 是 | `reports:view` | Query: `start_date`（必填）, `end_date`（必填）, `customer_id?`, `format=xlsx` | Excel 文件（销售统计，双 Sheet） |

---

## 15. 系统

| 方法 | 路径 | 鉴权 | RBAC | 响应 |
|------|------|------|------|------|
| GET | `/health` | 否 | 无 | `{"status":"ok","msg":"进销存系统 API 运行中"}` |
| GET | `/docs` | 否 | 无 | Swagger UI 页面（本地静态资源） |
| GET | `/redoc` | 否 | 无 | ReDoc 文档页面 |

---

## 错误码速查

| code | 含义 |
|------|------|
| 0 | 成功 |
| 400 | 请求参数错误 / 业务校验失败 |
| 401 | 未登录 / token 无效或过期（后端包装为 `code=40101`） |
| 40301 | 无权限（角色或权限码不足） |
| 404 | 资源不存在 |
| 40901 | 资源冲突（如用户名/编码已存在） |
