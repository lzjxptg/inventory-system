import request from './request'
import type { ApiResponse, Warehouse, WarehouseCreate, WarehouseUpdate } from '@/types'

export interface WarehouseQuery {
  skip?: number
  limit?: number
}

// 仓库列表
export function getWarehouses(params?: WarehouseQuery): Promise<ApiResponse<Warehouse[]>> {
  return request.get('/warehouses', { params })
}

// 仓库详情
export function getWarehouse(id: number): Promise<ApiResponse<Warehouse>> {
  return request.get(`/warehouses/${id}`)
}

// 新建仓库
export function createWarehouse(data: WarehouseCreate): Promise<ApiResponse<Warehouse>> {
  return request.post('/warehouses', data)
}

// 更新仓库
export function updateWarehouse(
  id: number,
  data: WarehouseUpdate,
): Promise<ApiResponse<Warehouse>> {
  return request.put(`/warehouses/${id}`, data)
}

// 删除仓库（逻辑删除）
export function deleteWarehouse(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/warehouses/${id}`)
}
