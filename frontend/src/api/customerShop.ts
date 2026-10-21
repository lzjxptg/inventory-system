import request from './request'
import type { ApiResponse, CustomerShop, CustomerShopCreate, CustomerShopUpdate } from '@/types'

// 客户门店列表（按客户ID筛选）
export function getCustomerShops(customer_id: number): Promise<ApiResponse<CustomerShop[]>> {
  return request.get('/customer-shops', { params: { customer_id } })
}

// 门店详情
export function getCustomerShop(id: number): Promise<ApiResponse<CustomerShop>> {
  return request.get(`/customer-shops/${id}`)
}

// 新建门店
export function createCustomerShop(data: CustomerShopCreate): Promise<ApiResponse<CustomerShop>> {
  return request.post('/customer-shops', data)
}

// 更新门店
export function updateCustomerShop(id: number, data: CustomerShopUpdate): Promise<ApiResponse<CustomerShop>> {
  return request.put(`/customer-shops/${id}`, data)
}

// 删除门店（逻辑删除）
export function deleteCustomerShop(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/customer-shops/${id}`)
}

// 设为默认门店
export function setDefaultShop(id: number): Promise<ApiResponse<CustomerShop>> {
  return request.post(`/customer-shops/${id}/set-default`)
}
