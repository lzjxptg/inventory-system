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
        </el-select>
      </el-form-item>
      <el-form-item label="起始日期">
        <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="截止日期">
        <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="product_name" label="商品" />
      <el-table-column prop="warehouse_name" label="仓库" />
      <el-table-column prop="movement_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.movement_type === 'IN' ? 'success' : 'danger'">{{ row.movement_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="120" />
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
import { getInventoryMovementsReport } from '@/api/reports'
import type { StockMovement } from '@/types'

const list = ref<StockMovement[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const productId = ref<number | undefined>(undefined)
const warehouseId = ref<number | undefined>(undefined)
const movementType = ref<string | undefined>(undefined)
const startDate = ref<string>('')
const endDate = ref<string>('')

async function load() {
  loading.value = true
  try {
    const res = await getInventoryMovementsReport({
      product_id: productId.value,
      warehouse_id: warehouseId.value,
      movement_type: movementType.value,
      start_date: startDate.value || undefined,
      end_date: endDate.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    list.value = res.data?.items || []
    total.value = res.data?.total || 0
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
  startDate.value = ''
  endDate.value = ''
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.filter-form {
  margin-bottom: 16px;
}
</style>
