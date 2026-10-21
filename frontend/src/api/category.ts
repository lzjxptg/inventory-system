import request from './request'
import type { ApiResponse, Category, CategoryCreate, CategoryUpdate, CategoryTreeNode } from '@/types'

export interface CategoryQuery {
  skip?: number
  limit?: number
}

// 分类列表（平铺）
export function getCategories(params?: CategoryQuery): Promise<ApiResponse<Category[]>> {
  return request.get('/categories', { params })
}

// 分类树形结构
export function getCategoryTree(): Promise<ApiResponse<CategoryTreeNode[]>> {
  return request.get('/categories/tree')
}

// 分类详情
export function getCategory(id: number): Promise<ApiResponse<Category>> {
  return request.get(`/categories/${id}`)
}

// 新建分类
export function createCategory(data: CategoryCreate): Promise<ApiResponse<Category>> {
  return request.post('/categories', data)
}

// 更新分类
export function updateCategory(id: number, data: CategoryUpdate): Promise<ApiResponse<Category>> {
  return request.put(`/categories/${id}`, data)
}

// 删除分类（逻辑删除）
export function deleteCategory(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/categories/${id}`)
}
