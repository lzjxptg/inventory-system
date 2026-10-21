import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
import type { ApiResponse, Supplier, SupplierCreate, SupplierUpdate } from '@/types'

export interface SupplierQuery {
  skip?: number
  limit?: number
}

// 供应商列表
export function getSuppliers(params?: SupplierQuery): Promise<ApiResponse<Supplier[]>> {
  return request.get('/suppliers', { params })
}

// 供应商详情
export function getSupplier(id: number): Promise<ApiResponse<Supplier>> {
  return request.get(`/suppliers/${id}`)
}

// 新建供应商
export function createSupplier(data: SupplierCreate): Promise<ApiResponse<Supplier>> {
  return request.post('/suppliers', data)
}

// 更新供应商
export function updateSupplier(id: number, data: SupplierUpdate): Promise<ApiResponse<Supplier>> {
  return request.put(`/suppliers/${id}`, data)
}

// 删除供应商（逻辑删除）
export function deleteSupplier(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/suppliers/${id}`)
}

// 导出供应商 Excel（axios 直连，绕过 request 响应拦截器）
// 注意：后端 GET /api/v1/suppliers/export 接口待实现
export function exportSuppliers(params?: Omit<SupplierQuery, 'skip' | 'limit'>): Promise<Blob> {
  return axios
    .get('/api/v1/suppliers/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}
