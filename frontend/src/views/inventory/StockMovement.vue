<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="商品ID">
        <el-input v-model.number="productId" placeholder="商品ID" clearable />
      </el-form-item>
      <el-form-item label="仓库ID">
        <el-input v-model.number="warehouseId" placeholder="仓库ID" clearable />
      </el-form-item>
      <el-form-item label="流水类型">
        <el-select v-model="movementType" placeholder="全部" clearable style="width: 120px">
          <el-option label="入库" value="IN" />
          <el-option label="出库" value="OUT" />
          <el-option label="盘点" value="ADJUST" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="warning" v-permission="'inventory:view'" @click="handleExport">导出 Excel</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="product_name" label="商品" />
      <el-table-column prop="warehouse_name" label="仓库" />
      <el-table-column prop="movement_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.movement_type)">{{ row.movement_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="120" />
      <el-table-column prop="operator_name" label="操作人" width="120" />
      <el-table-column prop="remark" label="备注" show-overflow-tooltip />
      <el-table-column prop="created_at" label="时间" width="180" />
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      :total="total"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="load"
      @current-change="load"
      style="margin-top: 16px; justify-content: flex-end"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getStockMovements, exportStockMovements } from '@/api/inventory'
import { downloadBlob } from '@/utils/download'
import type { StockMovement } from '@/types'

const list = ref<StockMovement[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const productId = ref<number | undefined>(undefined)
const warehouseId = ref<number | undefined>(undefined)
const movementType = ref<string | undefined>(undefined)

function typeTag(t: string): string {
  if (t === 'IN') return 'success'
  if (t === 'OUT') return 'danger'
  return 'warning'
}

async function load() {
  loading.value = true
  try {
    const res = await getStockMovements({
      product_id: productId.value,
      warehouse_id: warehouseId.value,
      movement_type: movementType.value,
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    list.value = res.data || []
    total.value = list.value.length >= pageSize.value ? page.value * pageSize.value + 1 : (page.value - 1) * pageSize.value + list.value.length
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  load()
}

function handleReset() {
  productId.value = undefined
  warehouseId.value = undefined
  movementType.value = undefined
  page.value = 1
  load()
}

async function handleExport() {
  try {
    const blob = await exportStockMovements({
      product_id: productId.value,
      warehouse_id: warehouseId.value,
      movement_type: movementType.value,
    })
    downloadBlob(blob, `库存流水_${Date.now()}.xlsx`)
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
</style>
