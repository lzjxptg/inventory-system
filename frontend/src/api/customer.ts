import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
import type { ApiResponse, Customer, CustomerCreate, CustomerUpdate } from '@/types'

export interface CustomerQuery {
  skip?: number
  limit?: number
}

// 客户列表
export function getCustomers(params?: CustomerQuery): Promise<ApiResponse<Customer[]>> {
  return request.get('/customers', { params })
}

// 客户详情
export function getCustomer(id: number): Promise<ApiResponse<Customer>> {
  return request.get(`/customers/${id}`)
}

// 新建客户
export function createCustomer(data: CustomerCreate): Promise<ApiResponse<Customer>> {
  return request.post('/customers', data)
}

// 更新客户
export function updateCustomer(id: number, data: CustomerUpdate): Promise<ApiResponse<Customer>> {
  return request.put(`/customers/${id}`, data)
}

// 删除客户（逻辑删除）
export function deleteCustomer(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/customers/${id}`)
}

// 导出客户 Excel（axios 直连，绕过 request 响应拦截器）
// 注意：后端 GET /api/v1/customers/export 接口待实现
export function exportCustomers(params?: Omit<CustomerQuery, 'skip' | 'limit'>): Promise<Blob> {
  return axios
    .get('/api/v1/customers/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}
