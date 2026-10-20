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

// 销售订单详情
export function getSalesOrder(id: number): Promise<ApiResponse<SalesOrder>> {
  return request.get(`/sales/orders/${id}`)
}
