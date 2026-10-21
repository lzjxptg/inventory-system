import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
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

// 导出采购订单 Excel（axios 直连，绕过 request 响应拦截器）
export function exportPurchaseOrders(params?: Omit<PurchaseOrderQuery, 'skip' | 'limit'>): Promise<Blob> {
  return axios
    .get('/api/v1/purchases/orders/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}

// 创建采购订单
export function createPurchaseOrder(data: PurchaseOrderCreate): Promise<ApiResponse<PurchaseOrder>> {
  return request.post('/purchases/orders', data)
}

// 采购订单详情（含明细）
export function getPurchaseOrder(id: number): Promise<ApiResponse<PurchaseOrder>> {
  return request.get(`/purchases/orders/${id}`)
}

// 更新采购订单（全量替换明细，仅草稿可改）
export function updatePurchaseOrder(id: number, data: PurchaseOrderCreate): Promise<ApiResponse<PurchaseOrder>> {
  return request.put(`/purchases/orders/${id}`, data)
}

// 删除采购订单（仅草稿可删，逻辑删除）
export function deletePurchaseOrder(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/purchases/orders/${id}`)
}

// 提交审核：draft -> submitted
export function submitPurchaseOrder(id: number): Promise<ApiResponse<PurchaseOrder>> {
  return request.post(`/purchases/orders/${id}/submit`)
}

// 审核通过：submitted -> approved
export function approvePurchaseOrder(id: number): Promise<ApiResponse<PurchaseOrder>> {
  return request.post(`/purchases/orders/${id}/approve`)
}

// 取消订单
export function cancelPurchaseOrder(id: number): Promise<ApiResponse<PurchaseOrder>> {
  return request.post(`/purchases/orders/${id}/cancel`)
}
