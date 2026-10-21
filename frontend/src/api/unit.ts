import request from './request'
import type { ApiResponse, Unit, UnitCreate, UnitUpdate } from '@/types'

export interface UnitQuery {
  skip?: number
  limit?: number
}

// 单位列表
export function getUnits(params?: UnitQuery): Promise<ApiResponse<Unit[]>> {
  return request.get('/units', { params })
}

// 单位详情
export function getUnit(id: number): Promise<ApiResponse<Unit>> {
  return request.get(`/units/${id}`)
}

// 新建单位
export function createUnit(data: UnitCreate): Promise<ApiResponse<Unit>> {
  return request.post('/units', data)
}

// 更新单位
export function updateUnit(id: number, data: UnitUpdate): Promise<ApiResponse<Unit>> {
  return request.put(`/units/${id}`, data)
}

// 删除单位（逻辑删除）
export function deleteUnit(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/units/${id}`)
}
