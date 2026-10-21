import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
import type {
  ApiResponse,
  PurchaseReturn,
  PurchaseReturnCreate,
  PurchaseReturnUpdate,
} from '@/types'

export interface PurchaseReturnQuery {
  status?: string
  supplier_id?: number
  keyword?: string
  skip?: number
  limit?: number
}

// 采购退货列表
export function getPurchaseReturns(
  params?: PurchaseReturnQuery,
): Promise<ApiResponse<PurchaseReturn[]>> {
  return request.get('/purchase-returns', { params })
}

// 采购退货详情
export function getPurchaseReturn(id: number): Promise<ApiResponse<PurchaseReturn>> {
  return request.get(`/purchase-returns/${id}`)
}

// 创建采购退货单
export function createPurchaseReturn(
  data: PurchaseReturnCreate,
): Promise<ApiResponse<PurchaseReturn>> {
  return request.post('/purchase-returns', data)
}

// 修改采购退货单（仅草稿）
export function updatePurchaseReturn(
  id: number,
  data: PurchaseReturnUpdate,
): Promise<ApiResponse<PurchaseReturn>> {
  return request.put(`/purchase-returns/${id}`, data)
}

// 删除采购退货单（仅草稿）
export function deletePurchaseReturn(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/purchase-returns/${id}`)
}

// 提交审核
export function submitPurchaseReturn(id: number): Promise<ApiResponse<PurchaseReturn>> {
  return request.post(`/purchase-returns/${id}/submit`)
}

// 审核通过
export function approvePurchaseReturn(id: number): Promise<ApiResponse<PurchaseReturn>> {
  return request.post(`/purchase-returns/${id}/approve`)
}

// 驳回
export function rejectPurchaseReturn(id: number): Promise<ApiResponse<PurchaseReturn>> {
  return request.post(`/purchase-returns/${id}/reject`)
}

// 导出 Excel
export function exportPurchaseReturns(
  params?: Omit<PurchaseReturnQuery, 'skip' | 'limit'>,
): Promise<Blob> {
  return axios
    .get('/api/v1/purchase-returns/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}
