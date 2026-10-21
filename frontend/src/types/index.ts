// 前端全部 TypeScript 类型定义

// 统一响应结构
export interface ApiResponse<T = any> {
  code: number
  msg: string
  data: T
}

// 通用分页结果
export interface PageResult<T = any> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ---------------- 鉴权 ----------------
export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface User {
  id: number
  username: string
  is_active?: boolean
  role_id?: number | null
  role?: string
  created_at?: string
}

// ---------------- 权限管理 ----------------
export interface Role {
  id: number
  name: string
  description: string
  is_deleted?: number
  created_at?: string
}

export interface Permission {
  id: number
  code: string
  name: string
  module: string
}

// ---------------- 库存 ----------------
export interface InventoryBalance {
  id: number
  product_id: number
  warehouse_id: number
  current_quantity: number
  product_name: string
  warehouse_name: string
  updated_at: string
  [key: string]: any
}

export interface StockMovement {
  id: number
  product_id: number
  warehouse_id: number
  movement_type: string
  quantity: number
  reference_type: string | null
  reference_id: number | null
  operator_id: number
  remark: string | null
  created_at: string
  product_name: string
  warehouse_name: string
  operator_name: string
  [key: string]: any
}

// ---------------- 采购 ----------------
export interface PurchaseOrder {
  id: number
  order_no: string
  supplier_id: number
  warehouse_id: number
  status: string
  total_quantity: number
  total_amount: number
  remark: string | null
  created_by: number
  approved_by: number | null
  created_at: string
  updated_at: string
  supplier_name: string
  warehouse_name: string
  items: any[]
  [key: string]: any
}

export interface PurchaseOrderItemCreate {
  product_id: number
  quantity: number
  unit_price: number
  remark?: string | null
}

export interface PurchaseOrderCreate {
  supplier_id: number
  warehouse_id: number
  remark?: string | null
  items: PurchaseOrderItemCreate[]
}

// ---------------- 销售 ----------------
export interface SalesOrder {
  id: number
  order_no: string
  customer_id: number
  warehouse_id: number
  status: string
  total_quantity: number
  total_amount: number
  remark: string | null
  created_by: number
  approved_by: number | null
  created_at: string
  updated_at: string
  customer_name: string
  warehouse_name: string
  items: any[]
  [key: string]: any
}

export interface SalesOrderItemCreate {
  product_id: number
  quantity: number
  unit_price: number
  remark?: string | null
}

export interface SalesOrderCreate {
  customer_id: number
  warehouse_id: number
  remark?: string | null
  items: SalesOrderItemCreate[]
}

// ---------------- 报表 ----------------
export interface LowStockAlertItem {
  product_id: number
  product_name: string
  warehouse_id: number
  warehouse_name: string
  current_quantity: number
  alert_threshold: number
}

export interface PurchaseSummaryData {
  total_orders: number
  total_items: number
  total_amount: number
  total_quantity: number
  by_supplier: Array<{
    supplier_id: number
    supplier_name: string
    order_count: number
    total_amount: number
  }>
}

export interface SalesSummaryData {
  total_orders: number
  total_items: number
  total_amount: number
  total_quantity: number
  by_customer: Array<{
    customer_id: number
    customer_name: string
    order_count: number
    total_amount: number
  }>
}

// ---------------- 商品 ----------------
export interface Product {
  id: number
  sku: string
  name: string
  category_id: number | null
  unit_id: number
  spec: string | null
  purchase_price: number
  sale_price: number
  min_stock: number
  status: number
  is_deleted: number
  created_at: string
  updated_at: string
  [key: string]: any
}

export interface ProductCreate {
  sku: string
  name: string
  category_id?: number | null
  unit_id: number
  spec?: string | null
  purchase_price?: number
  sale_price?: number
  min_stock?: number
  status?: number
}

export interface ProductUpdate {
  sku?: string
  name?: string
  category_id?: number | null
  unit_id?: number
  spec?: string | null
  purchase_price?: number
  sale_price?: number
  min_stock?: number
  status?: number
}

// ---------------- 仓库 ----------------
export interface Warehouse {
  id: number
  code: string
  name: string
  manager: string | null
  is_deleted: number
  created_at: string
  [key: string]: any
}

export interface WarehouseCreate {
  code: string
  name: string
  manager?: string | null
}

export interface WarehouseUpdate {
  code?: string
  name?: string
  manager?: string | null
}

// ---------------- 分类 ----------------
export interface Category {
  id: number
  name: string
  parent_id: number | null
  sort: number
  is_deleted: number
  created_at: string
}

// ---------------- 单位 ----------------
export interface Unit {
  id: number
  name: string
  code: string | null
  sort: number
  is_deleted: number
  created_at: string
}

// ---------------- 供应商 ----------------
export interface Supplier {
  id: number
  code: string
  name: string
  contact: string | null
  phone: string | null
  address: string | null
  is_deleted: number
  created_at: string
  [key: string]: any
}

export interface SupplierCreate {
  code: string
  name: string
  contact?: string | null
  phone?: string | null
  address?: string | null
}

export interface SupplierUpdate {
  code?: string
  name?: string
  contact?: string | null
  phone?: string | null
  address?: string | null
}

// ---------------- 客户 ----------------
export interface Customer {
  id: number
  code: string
  name: string
  contact: string | null
  phone: string | null
  address: string | null
  is_deleted: number
  created_at: string
  [key: string]: any
}

export interface CustomerCreate {
  code: string
  name: string
  contact?: string | null
  phone?: string | null
  address?: string | null
}

export interface CustomerUpdate {
  code?: string
  name?: string
  contact?: string | null
  phone?: string | null
  address?: string | null
}
