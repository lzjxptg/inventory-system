<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="起始日期">
        <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="截止日期">
        <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="供应商ID">
        <el-input v-model.number="supplierId" placeholder="供应商ID" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :disabled="!canQuery" @click="load">查询</el-button>
        <el-button type="warning" v-permission="'reports:view'" :disabled="!canQuery" @click="handleExport">导出 Excel</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">采购订单数</div>
          <div class="stat-value">{{ summary.total_orders }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">明细数</div>
          <div class="stat-value">{{ summary.total_items }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">总金额</div>
          <div class="stat-value">¥ {{ Number(summary.total_amount || 0).toFixed(2) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">总数量</div>
          <div class="stat-value">{{ Number(summary.total_quantity || 0).toFixed(2) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>按供应商分组</template>
      <v-chart v-if="hasData" class="chart" :option="chartOption" autoresize />
      <el-empty v-else description="暂无数据，请选择日期范围后查询" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { getPurchaseSummary, exportPurchaseSummary } from '@/api/reports'
import { downloadBlob } from '@/utils/download'
import type { PurchaseSummaryData } from '@/types'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const now = new Date()
const startDate = ref(new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10))
const endDate = ref(now.toISOString().slice(0, 10))
const supplierId = ref<number | undefined>(undefined)

const summary = ref<PurchaseSummaryData>({
  total_orders: 0,
  total_items: 0,
  total_amount: 0,
  total_quantity: 0,
  by_supplier: [],
})

const canQuery = computed(() => !!startDate.value && !!endDate.value)
const hasData = computed(() => summary.value.by_supplier.length > 0)

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 20, bottom: 40 },
  xAxis: {
    type: 'category',
    data: summary.value.by_supplier.map((i) => i.supplier_name),
    axisLabel: { interval: 0, rotate: summary.value.by_supplier.length > 5 ? 30 : 0 },
  },
  yAxis: { type: 'value' },
  series: [
    {
      type: 'bar',
      data: summary.value.by_supplier.map((i) => Number(i.total_amount)),
      itemStyle: { color: '#409EFF' },
      barMaxWidth: 40,
    },
  ],
}))

async function load() {
  if (!canQuery.value) return
  try {
    const res = await getPurchaseSummary({
      start_date: startDate.value,
      end_date: endDate.value,
      supplier_id: supplierId.value,
    })
    summary.value = res.data || summary.value
  } catch {
    /* 错误由拦截器统一提示 */
  }
}

async function handleExport() {
  if (!canQuery.value) {
    ElMessage.warning('请选择起始和截止日期')
    return
  }
  try {
    const blob = await exportPurchaseSummary({
      start_date: startDate.value,
      end_date: endDate.value,
      supplier_id: supplierId.value,
    })
    downloadBlob(blob, `采购统计_${Date.now()}.xlsx`)
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(load)
</script>

<style scoped>
.filter-form {
  margin-bottom: 16px;
}
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
  font-size: 22px;
  font-weight: 600;
}
.chart {
  height: 360px;
}
</style>
