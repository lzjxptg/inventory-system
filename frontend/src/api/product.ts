import request from './request'
import type {
  ApiResponse,
  Product,
  ProductCreate,
  ProductUpdate,
  Category,
  Unit,
} from '@/types'

export interface ProductQuery {
  skip?: number
  limit?: number
}

// 商品列表
export function getProducts(params?: ProductQuery): Promise<ApiResponse<Product[]>> {
  return request.get('/products', { params })
}

// 商品详情
export function getProduct(id: number): Promise<ApiResponse<Product>> {
  return request.get(`/products/${id}`)
}

// 新建商品
export function createProduct(data: ProductCreate): Promise<ApiResponse<Product>> {
  return request.post('/products', data)
}

// 更新商品
export function updateProduct(id: number, data: ProductUpdate): Promise<ApiResponse<Product>> {
  return request.put(`/products/${id}`, data)
}

// 删除商品（逻辑删除）
export function deleteProduct(id: number): Promise<ApiResponse<null>> {
  return request.delete(`/products/${id}`)
}

// 分类列表（商品表单下拉用）
export function getCategories(): Promise<ApiResponse<Category[]>> {
  return request.get('/categories', { params: { skip: 0, limit: 1000 } })
}

// 单位列表（商品表单下拉用）
export function getUnits(): Promise<ApiResponse<Unit[]>> {
  return request.get('/units', { params: { skip: 0, limit: 1000 } })
}
