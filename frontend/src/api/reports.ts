import axios from 'axios'
import request from './request'
import { getToken } from '@/utils/auth'
import type {
  ApiResponse,
  PageResult,
  LowStockAlertItem,
  StockMovement,
  PurchaseSummaryData,
  SalesSummaryData,
} from '@/types'

export interface MovementReportQuery {
  product_id?: number
  warehouse_id?: number
  movement_type?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export interface LowStockQuery {
  warehouse_id?: number
  page?: number
  page_size?: number
}

export interface DateRangeQuery {
  start_date: string
  end_date: string
  supplier_id?: number
  customer_id?: number
}

// 库存流水汇总（分页）
export function getInventoryMovementsReport(
  params?: MovementReportQuery,
): Promise<ApiResponse<PageResult<StockMovement>>> {
  return request.get('/reports/inventory-movements', { params })
}

// 低库存预警
export function getLowStockAlerts(params?: LowStockQuery): Promise<ApiResponse<PageResult<LowStockAlertItem>>> {
  return request.get('/reports/low-stock-alerts', { params })
}

// 采购金额统计（必填 start_date / end_date）
export function getPurchaseSummary(
  params: Pick<DateRangeQuery, 'start_date' | 'end_date' | 'supplier_id'>,
): Promise<ApiResponse<PurchaseSummaryData>> {
  return request.get('/reports/purchase-summary', { params })
}

// 销售金额统计（必填 start_date / end_date）
export function getSalesSummary(
  params: Pick<DateRangeQuery, 'start_date' | 'end_date' | 'customer_id'>,
): Promise<ApiResponse<SalesSummaryData>> {
  return request.get('/reports/sales-summary', { params })
}

// 导出低库存预警 Excel（axios 直连，绕过 request 响应拦截器）
export function exportLowStockAlerts(params?: Omit<LowStockQuery, 'page' | 'page_size'>): Promise<Blob> {
  return axios
    .get('/api/v1/reports/low-stock-alerts/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}

// 导出采购统计 Excel
export function exportPurchaseSummary(
  params: Pick<DateRangeQuery, 'start_date' | 'end_date' | 'supplier_id'>,
): Promise<Blob> {
  return axios
    .get('/api/v1/reports/purchase-summary/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}

// 导出销售统计 Excel
export function exportSalesSummary(
  params: Pick<DateRangeQuery, 'start_date' | 'end_date' | 'customer_id'>,
): Promise<Blob> {
  return axios
    .get('/api/v1/reports/sales-summary/export', {
      params,
      responseType: 'blob',
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    .then((res) => res.data as Blob)
}
