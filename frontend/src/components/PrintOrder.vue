<template>
  <div class="print-order">
    <div class="print-area" ref="printArea">
      <h1 class="bill-title">{{ title }}</h1>

      <div class="bill-info">
        <div class="info-row">
          <span class="label">单据编号：</span>
          <span class="value">{{ order.order_no }}</span>
          <span class="label" style="margin-left: 40px">日期：</span>
          <span class="value">{{ formatDate(order.created_at) }}</span>
        </div>
        <div class="info-row">
          <template v-if="type === 'purchase'">
            <span class="label">供应商：</span>
            <span class="value">{{ order.supplier_name || '-' }}</span>
          </template>
          <template v-else>
            <span class="label">客户：</span>
            <span class="value">{{ order.customer_name || '-' }}</span>
          </template>
          <span class="label" style="margin-left: 40px">仓库：</span>
          <span class="value">{{ order.warehouse_name || '-' }}</span>
        </div>

        <div v-if="type === 'sales'" class="shop-info">
          <div><span class="label">送货门店：</span><span class="value">{{ order.shop_name || '-' }}</span></div>
          <div><span class="label">门店地址：</span><span class="value">{{ order.shop_address || '-' }}</span></div>
          <div><span class="label">联系人：</span><span class="value">{{ order.shop_contact || '-' }}</span></div>
          <div><span class="label">联系电话：</span><span class="value">{{ order.shop_phone || '-' }}</span></div>
        </div>
      </div>

      <table class="bill-table">
        <thead>
          <tr>
            <th style="width: 50px">序号</th>
            <th style="width: 120px">商品编码</th>
            <th>商品名称</th>
            <th style="width: 70px">单位</th>
            <th style="width: 90px">数量</th>
            <th style="width: 100px">单价</th>
            <th style="width: 120px">金额</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in order.items" :key="item.id">
            <td class="center">{{ index + 1 }}</td>
            <td>{{ item.product_sku || '-' }}</td>
            <td>{{ item.product_name || '-' }}</td>
            <td class="center">{{ item.unit_name || '-' }}</td>
            <td class="right">{{ formatNum(item.quantity) }}</td>
            <td class="right">{{ formatNum(item.unit_price) }}</td>
            <td class="right">{{ formatNum(item.amount) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="4" class="right bold">合计</td>
            <td class="right bold">{{ formatNum(order.total_quantity) }}</td>
            <td class="right bold"></td>
            <td class="right bold">¥{{ formatNum(order.total_amount) }}</td>
          </tr>
        </tfoot>
      </table>

      <div class="bill-footer">
        <div class="footer-row">
          <span>制单人：{{ order.created_by_name || '-' }}</span>
          <span>审核人：{{ order.approved_by_name || '-' }}</span>
          <span>打印日期：{{ today }}</span>
        </div>
      </div>

      <div class="company-footer">进销存管理系统</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface PrintItem {
  id: number
  product_sku?: string
  product_name?: string
  unit_name?: string
  quantity: number | string
  unit_price: number | string
  amount: number | string
}

interface PrintOrderData {
  order_no: string
  created_at: string
  status: string
  total_quantity: number | string
  total_amount: number | string
  remark?: string | null
  created_by_name?: string
  approved_by_name?: string
  supplier_name?: string
  customer_name?: string
  warehouse_name?: string
  shop_name?: string
  shop_address?: string
  shop_contact?: string
  shop_phone?: string
  items: PrintItem[]
  [key: string]: any
}

const props = defineProps<{
  type: 'purchase' | 'sales'
  order: PrintOrderData
}>()

const title = computed(() => (props.type === 'purchase' ? '采购单' : '销售出库单'))

const today = new Date().toISOString().slice(0, 10)

function formatDate(s: string): string {
  if (!s) return '-'
  return s.slice(0, 10)
}

function formatNum(v: number | string): string {
  if (v === null || v === undefined || v === '') return '0'
  const n = typeof v === 'string' ? parseFloat(v) : v
  if (isNaN(n)) return String(v)
  return n.toFixed(2)
}
</script>

<style scoped>
.print-order {
  padding: 16px;
}

.print-area {
  background: #fff;
  padding: 20px;
  border: 1px solid #ddd;
  font-family: "Microsoft YaHei", "SimSun", sans-serif;
  font-size: 13px;
  color: #000;
}

.bill-title {
  text-align: center;
  font-size: 24px;
  font-weight: bold;
  margin: 0 0 20px 0;
  letter-spacing: 8px;
}

.bill-info {
  margin-bottom: 16px;
  line-height: 2;
}

.info-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.label {
  font-weight: bold;
}

.value {
  display: inline-block;
  min-width: 80px;
}

.shop-info {
  margin-top: 4px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px 20px;
}

.bill-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 16px;
}

.bill-table th,
.bill-table td {
  border: 1px solid #333;
  padding: 6px 8px;
  text-align: left;
}

.bill-table th {
  background: #f5f5f5;
  font-weight: bold;
}

.bill-table .center {
  text-align: center;
}

.bill-table .right {
  text-align: right;
}

.bill-table .bold {
  font-weight: bold;
}

.bill-footer {
  margin-top: 24px;
  padding-top: 12px;
  border-top: 1px dashed #999;
}

.footer-row {
  display: flex;
  justify-content: space-between;
}

.company-footer {
  text-align: center;
  color: #999;
  font-size: 11px;
  margin-top: 30px;
}
</style>

<style>
/* 全局打印样式：仅打印 .print-area 区域 */
@media print {
  body * {
    visibility: hidden;
  }
  .print-area,
  .print-area * {
    visibility: visible;
  }
  .print-area {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    padding: 0;
    border: none;
  }
  .el-dialog__wrapper,
  .el-overlay,
  .el-popper {
    display: none !important;
  }
  @page {
    size: A4;
    margin: 15mm;
  }
}
</style>
