<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">低库存预警</div>
          <div class="stat-value">{{ lowStockCount }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">本月采购额</div>
          <div class="stat-value">¥ {{ purchaseAmount }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">本月销售额</div>
          <div class="stat-value">¥ {{ salesAmount }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">库存流水数</div>
          <div class="stat-value">{{ movementCount }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>采购金额趋势（按供应商）</template>
          <v-chart class="chart" :option="purchaseOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>销售金额趋势（按客户）</template>
          <v-chart class="chart" :option="salesOption" autoresize />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  getLowStockAlerts,
  getPurchaseSummary,
  getSalesSummary,
  getInventoryMovementsReport,
} from '@/api/reports'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const lowStockCount = ref(0)
const purchaseAmount = ref('0.00')
const salesAmount = ref('0.00')
const movementCount = ref(0)

const purchaseOption = ref<any>({})
const salesOption = ref<any>({})

const dateRange = computed(() => {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  return { start_date: fmt(start), end_date: fmt(now) }
})

function buildBarOption(names: string[], values: number[], color: string) {
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: names.length > 5 ? 30 : 0 } },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        data: values,
        itemStyle: { color },
        barMaxWidth: 40,
      },
    ],
  }
}

async function loadDashboard() {
  try {
    const [lowStock, purchase, sales, movements] = await Promise.all([
      getLowStockAlerts({ page: 1, page_size: 1 }).catch(() => ({ data: { total: 0 } } as any)),
      getPurchaseSummary(dateRange.value).catch(() => ({ data: { total_amount: 0, by_supplier: [] } } as any)),
      getSalesSummary(dateRange.value).catch(() => ({ data: { total_amount: 0, by_customer: [] } } as any)),
      getInventoryMovementsReport({ page: 1, page_size: 1 }).catch(() => ({ data: { total: 0 } } as any)),
    ])

    lowStockCount.value = lowStock.data?.total ?? 0
    purchaseAmount.value = Number(purchase.data?.total_amount ?? 0).toFixed(2)
    salesAmount.value = Number(sales.data?.total_amount ?? 0).toFixed(2)
    movementCount.value = movements.data?.total ?? 0

    const supplierNames = (purchase.data?.by_supplier || []).map((i: any) => i.supplier_name)
    const supplierValues = (purchase.data?.by_supplier || []).map((i: any) => Number(i.total_amount))
    purchaseOption.value = buildBarOption(supplierNames, supplierValues, '#409EFF')

    const customerNames = (sales.data?.by_customer || []).map((i: any) => i.customer_name)
    const customerValues = (sales.data?.by_customer || []).map((i: any) => Number(i.total_amount))
    salesOption.value = buildBarOption(customerNames, customerValues, '#67C23A')
  } catch (e) {
    console.error('仪表盘加载失败', e)
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.stat-card {
  text-align: center;
}
.stat-label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 8px;
}
.stat-value {
  color: #303133;
  font-size: 26px;
  font-weight: 600;
}
.chart {
  height: 320px;
}
</style>
