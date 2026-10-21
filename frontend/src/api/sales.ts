import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
import type { ApiResponse, SalesOrder, SalesOrderCreate } from '@/types'

export interface SalesOrderQuery {
  status?: string
  customer_id?: number
  keyword?: string
  skip?: number
  limit?: number
}

// 销售订单列表
export function getSalesOrders(params?: SalesOrderQuery): Promise<ApiResponse<SalesOrder[]>> {
  return request.get('/sales/orders', { params })
}

// 导出销售订单 Excel（axios 直连，绕过 request 响应拦截器）
export function exportSalesOrders(params?: Omit<SalesOrderQuery, 'skip' | 'limit'>): Promise<Blob> {
  return axios
    .get('/api/v1/sales/orders/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}

// 创建销售订单
export function createSalesOrder(data: SalesOrderCreate): Promise<ApiResponse<SalesOrder>> {
  return request.post('/sales/orders', data)
}

// 销售订单详情（含明细）
export function getSalesOrder(id: number): Promise<ApiResponse<SalesOrder>> {
  return request.get(`/sales/orders/${id}`)
}

// 更新销售订单（全量替换明细，仅草稿可改）
export function updateSalesOrder(id: number, data: SalesOrderCreate): Promise<ApiResponse<SalesOrder>> {
  return request.put(`/sales/orders/${id}`, data)
}

// 删除销售订单（仅草稿可删，逻辑删除）
export function deleteSalesOrder(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/sales/orders/${id}`)
}

// 提交审核：draft -> submitted
export function submitSalesOrder(id: number): Promise<ApiResponse<SalesOrder>> {
  return request.post(`/sales/orders/${id}/submit`)
}

// 审核通过：submitted -> approved
export function approveSalesOrder(id: number): Promise<ApiResponse<SalesOrder>> {
  return request.post(`/sales/orders/${id}/approve`)
}

// 取消订单
export function cancelSalesOrder(id: number): Promise<ApiResponse<SalesOrder>> {
  return request.post(`/sales/orders/${id}/cancel`)
}
