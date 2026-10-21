import request from './request'
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
