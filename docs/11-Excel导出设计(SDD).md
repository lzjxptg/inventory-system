# Excel 导出功能设计 (SDD)

> 版本：v1.0
> 适用阶段：库存流水、采购订单、销售订单、低库存预警、采购统计、销售统计 6 个模块的 Excel 导出
> 依赖：openpyxl（生成 .xlsx）、FastAPI StreamingResponse

## 1. 概述

为进销存系统的 6 个列表/报表页面增加「导出 Excel」能力，便于离线查看与二次加工。

### 1.1 范围

| 序号 | 模块 | 前端页面 | 导出接口 | 数据来源 CRUD |
|------|------|----------|----------|---------------|
| 1 | 库存流水 | `views/inventory/StockMovement.vue` | `GET /api/v1/inventory/movements/export` | `crud.inventory.get_movements` |
| 2 | 采购订单列表 | `views/purchase/PurchaseOrders.vue` | `GET /api/v1/purchases/orders/export` | `crud.purchase.list_orders` |
| 3 | 销售订单列表 | `views/sales/SalesOrders.vue` | `GET /api/v1/sales/orders/export` | `crud.sales.list_orders` |
| 4 | 低库存预警 | `views/reports/LowStockAlerts.vue` | `GET /api/v1/reports/low-stock-alerts/export` | `crud.reports.get_low_stock_alerts` |
| 5 | 采购统计 | `views/reports/PurchaseSummary.vue` | `GET /api/v1/reports/purchase-summary/export` | `crud.reports.get_purchase_summary` |
| 6 | 销售统计 | `views/reports/SalesSummary.vue` | `GET /api/v1/reports/sales-summary/export` | `crud.reports.get_sales_summary` |

### 1.2 非目标

- 不导出库存余额（StockList）页面。
- 不新增导出文件存储（不落盘），仅流式返回。
- 不修改现有列表接口。

## 2. 后端设计

### 2.1 依赖

- `requirements.txt` 新增 `openpyxl>=3.1.0`。

### 2.2 通用导出工具 `core/excel_export.py`

提供两个工具函数，避免各路由重复造轮子：

```python
from fastapi import Response
from openpyxl import Workbook

def build_excel_bytes(headers: list[str], rows: list[list]) -> bytes:
    """构建 xlsx 字节流。headers 为表头，rows 为数据行（与表头一一对应）。"""

def excel_response(data: bytes, filename: str) -> Response:
    """返回带正确 Content-Type / Content-Disposition 的流式响应。"""
```

- `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `Content-Disposition: attachment; filename*=UTF-8''{urlquote(filename)}`
- 文件名格式：`{业务名}_{YYYYMMDDHHMMSS}.xlsx`

### 2.3 导出数据获取

- 复用现有 CRUD 函数，**去掉分页参数**（`skip`/`limit` 或 `page`/`page_size`）：
  - `skip/limit` 型：传 `skip=0, limit=100000`。
  - `page/page_size` 型：传 `page=1, page_size=100000`。
- 其余筛选参数与对应列表接口完全一致。
- 导出数据量 = 列表接口在相同筛选条件下的全部匹配数据（去分页限制）。

### 2.4 列定义（表头 ↔ 字段映射）

#### 2.4.1 库存流水
| 表头 | 字段 |
|------|------|
| ID | id |
| 商品 | product_name |
| 仓库 | warehouse_name |
| 类型 | movement_type |
| 数量 | quantity |
| 关联类型 | reference_type |
| 关联单号 | reference_no |
| 操作人 | operator_name |
| 备注 | remark |
| 时间 | created_at |

#### 2.4.2 采购订单
| 表头 | 字段 |
|------|------|
| ID | id |
| 订单号 | order_no |
| 供应商 | supplier_name |
| 仓库 | warehouse_name |
| 状态 | status |
| 总数量 | total_quantity |
| 总金额 | total_amount |
| 备注 | remark |
| 创建时间 | created_at |

#### 2.4.3 销售订单
| 表头 | 字段 |
|------|------|
| ID | id |
| 订单号 | order_no |
| 客户 | customer_name |
| 仓库 | warehouse_name |
| 状态 | status |
| 总数量 | total_quantity |
| 总金额 | total_amount |
| 备注 | remark |
| 创建时间 | created_at |

#### 2.4.4 低库存预警
| 表头 | 字段 |
|------|------|
| 商品ID | product_id |
| 商品名称 | product_name |
| 仓库ID | warehouse_id |
| 仓库名称 | warehouse_name |
| 当前库存 | current_quantity |
| 预警阈值 | alert_threshold |

#### 2.4.5 采购统计（两个 Sheet）
- Sheet 1「汇总」：采购订单数 / 明细数 / 总金额 / 总数量（单行）。
- Sheet 2「按供应商分组」：供应商ID / 供应商名称 / 订单数 / 总金额 / 总数量。

#### 2.4.6 销售统计（两个 Sheet）
- Sheet 1「汇总」：销售订单数 / 明细数 / 总金额 / 总数量（单行）。
- Sheet 2「按客户分组」：客户ID / 客户名称 / 订单数 / 总金额 / 总数量。

### 2.5 权限控制

各导出端点使用 `require_permission(perm_code)` 依赖，复用现有查看类权限码：

| 端点 | 权限码 |
|------|--------|
| `/inventory/movements/export` | `inventory:view` |
| `/purchases/orders/export` | `purchase:view` |
| `/sales/orders/export` | `sales:view` |
| `/reports/low-stock-alerts/export` | `reports:view` |
| `/reports/purchase-summary/export` | `reports:view` |
| `/reports/sales-summary/export` | `reports:view` |

`operator` 角色已拥有上述全部权限，admin 拥有全部权限。

### 2.6 敏感字段

- 不导出用户密码、token 等超管敏感字段。
- 不导出 `is_deleted` 等内部字段。

## 3. 接口契约

### 3.1 通用响应

- Method：`GET`
- 认证：`Authorization: Bearer <token>`（依赖 `get_current_user`）
- 响应体：`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` 二进制流
- 响应头：`Content-Disposition: attachment; filename*=UTF-8''库存流水_20250101120000.xlsx`

### 3.2 各端点 Query 参数

| 端点 | Query 参数 |
|------|-----------|
| `/inventory/movements/export` | `product_id?`, `warehouse_id?`, `movement_type?` |
| `/purchases/orders/export` | `status?`, `supplier_id?`, `keyword?` |
| `/sales/orders/export` | `status?`, `customer_id?`, `keyword?` |
| `/reports/low-stock-alerts/export` | `warehouse_id?` |
| `/reports/purchase-summary/export` | `start_date`(必填), `end_date`(必填), `supplier_id?` |
| `/reports/sales-summary/export` | `start_date`(必填), `end_date`(必填), `customer_id?` |

### 3.3 错误处理

- 鉴权失败：401 / 403（由 `get_current_user` / `require_permission` 抛出，统一异常处理）。
- 参数校验失败（如统计缺日期）：422，由 FastAPI 自动处理。
- 无数据：仍返回仅含表头的 xlsx（状态 200）。

## 4. 前端设计

### 4.1 API 层

在 `frontend/src/api/` 对应文件追加导出函数，统一约定：

```ts
import axios from 'axios'
import { getToken } from '@/utils/auth'

export function exportStockMovements(params?: MovementQuery): Promise<Blob> {
  return axios
    .get('/api/v1/inventory/movements/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}
```

- **导出接口走 axios 直连（绕过 `request.ts` 响应拦截器），与登录接口方案一致。**
  `request.ts` 的响应拦截器会按 `{code,msg,data}` 解包，遇到二进制 Blob 会解析失败。
- API 函数返回原始 `response.data`（即 Blob），调用方直接拿到 Blob。
- 必须显式传 `responseType: 'blob'`，并手动携带 `Authorization` header。
- 入参 = 对应列表查询参数（去分页字段）。

### 4.2 下载工具 `frontend/src/utils/download.ts`

新增通用下载函数，解析响应头文件名：

```ts
export function downloadBlob(blob: Blob, filename?: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'export.xlsx'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
```

### 4.3 视图层

在 6 个页面的筛选区按钮组中追加「导出 Excel」按钮：

```html
<el-button type="warning" v-permission="'inventory:view'" @click="handleExport">导出 Excel</el-button>
```

- `v-permission` 权限码与后端一致（查看类），保证 operator 可见。
- 点击逻辑：调用对应 export 函数 → `downloadBlob(res.data)`。
- 统计页导出前校验日期必填，与查询逻辑一致。

### 4.4 权限码对照

| 页面 | v-permission |
|------|--------------|
| StockMovement.vue | `inventory:view` |
| PurchaseOrders.vue | `purchase:view` |
| SalesOrders.vue | `sales:view` |
| LowStockAlerts.vue | `reports:view` |
| PurchaseSummary.vue | `reports:view` |
| SalesSummary.vue | `reports:view` |

## 5. 测试设计

### 5.1 后端测试 `tests/test_export.py`

为 6 个导出端点各写 1 个用例，断言：

1. 返回 200。
2. `Content-Type` 包含 `spreadsheetml.sheet`。
3. `Content-Disposition` 含 `attachment` 且文件名以 `.xlsx` 结尾。
4. 响应体可被 `openpyxl.load_workbook` 正常打开，且至少 1 个 sheet。

### 5.2 回归

- 现有 131 个测试必须全部通过。
- 不修改现有列表接口，确保兼容性。

## 6. 约束与风险

1. 大数据量导出暂未做异步流式分片（单次 10w 行以内可接受）。
2. 导出接口不缓存、不落盘，每次请求实时生成。
3. 文件名使用服务器本地时间（与系统时间规范一致）。
