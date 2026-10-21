import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
import type {
  ApiResponse,
  SalesReturn,
  SalesReturnCreate,
  SalesReturnUpdate,
} from '@/types'

export interface SalesReturnQuery {
  status?: string
  customer_id?: number
  keyword?: string
  skip?: number
  limit?: number
}

// 销售退货列表
export function getSalesReturns(
  params?: SalesReturnQuery,
): Promise<ApiResponse<SalesReturn[]>> {
  return request.get('/sales-returns', { params })
}

// 销售退货详情
export function getSalesReturn(id: number): Promise<ApiResponse<SalesReturn>> {
  return request.get(`/sales-returns/${id}`)
}

// 创建销售退货单
export function createSalesReturn(
  data: SalesReturnCreate,
): Promise<ApiResponse<SalesReturn>> {
  return request.post('/sales-returns', data)
}

// 修改销售退货单（仅草稿）
export function updateSalesReturn(
  id: number,
  data: SalesReturnUpdate,
): Promise<ApiResponse<SalesReturn>> {
  return request.put(`/sales-returns/${id}`, data)
}

// 删除销售退货单（仅草稿）
export function deleteSalesReturn(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/sales-returns/${id}`)
}

// 提交审核
export function submitSalesReturn(id: number): Promise<ApiResponse<SalesReturn>> {
  return request.post(`/sales-returns/${id}/submit`)
}

// 审核通过
export function approveSalesReturn(id: number): Promise<ApiResponse<SalesReturn>> {
  return request.post(`/sales-returns/${id}/approve`)
}

// 驳回
export function rejectSalesReturn(id: number): Promise<ApiResponse<SalesReturn>> {
  return request.post(`/sales-returns/${id}/reject`)
}

// 导出 Excel
export function exportSalesReturns(
  params?: Omit<SalesReturnQuery, 'skip' | 'limit'>,
): Promise<Blob> {
  return axios
    .get('/api/v1/sales-returns/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}
