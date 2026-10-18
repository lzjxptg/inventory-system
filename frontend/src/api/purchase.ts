import request from './request'
import type { ApiResponse, PurchaseOrder, PurchaseOrderCreate } from '@/types'

export interface PurchaseOrderQuery {
  status?: string
  supplier_id?: number
  keyword?: string
  skip?: number
  limit?: number
}

// 采购订单列表
export function getPurchaseOrders(params?: PurchaseOrderQuery): Promise<ApiResponse<PurchaseOrder[]>> {
  return request.get('/purchases/orders', { params })
}

// 创建采购订单
export function createPurchaseOrder(data: PurchaseOrderCreate): Promise<ApiResponse<PurchaseOrder>> {
  return request.post('/purchases/orders', data)
}

// 采购订单详情
export function getPurchaseOrder(id: number): Promise<ApiResponse<PurchaseOrder>> {
  return request.get(`/purchases/orders/${id}`)
}
