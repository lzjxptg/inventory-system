import request from './request'
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

// 创建销售订单
export function createSalesOrder(data: SalesOrderCreate): Promise<ApiResponse<SalesOrder>> {
  return request.post('/sales/orders', data)
}

// 销售订单详情
export function getSalesOrder(id: number): Promise<ApiResponse<SalesOrder>> {
  return request.get(`/sales/orders/${id}`)
}
