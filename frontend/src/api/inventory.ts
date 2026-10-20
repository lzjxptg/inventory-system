import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
import type { ApiResponse, InventoryBalance, StockMovement } from '@/types'

export interface BalanceQuery {
  product_id?: number
  warehouse_id?: number
  skip?: number
  limit?: number
}

export interface MovementQuery {
  product_id?: number
  warehouse_id?: number
  movement_type?: string
  skip?: number
  limit?: number
}

// 库存余额列表（后端返回 data 为数组，skip/limit 分页）
export function getInventoryBalances(params?: BalanceQuery): Promise<ApiResponse<InventoryBalance[]>> {
  return request.get('/inventory/balances', { params })
}

// 库存流水列表
export function getStockMovements(params?: MovementQuery): Promise<ApiResponse<StockMovement[]>> {
  return request.get('/inventory/movements', { params })
}

// 导出库存流水 Excel（axios 直连，绕过 request 响应拦截器）
export function exportStockMovements(params?: Omit<MovementQuery, 'skip' | 'limit'>): Promise<Blob> {
  return axios
    .get('/api/v1/inventory/movements/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}
