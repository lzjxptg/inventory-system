<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="商品ID">
        <el-input v-model.number="productId" placeholder="商品ID" clearable />
      </el-form-item>
      <el-form-item label="仓库ID">
        <el-input v-model.number="warehouseId" placeholder="仓库ID" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="product_id" label="商品ID" width="100" />
      <el-table-column prop="product_name" label="商品名称" />
      <el-table-column prop="warehouse_id" label="仓库ID" width="100" />
      <el-table-column prop="warehouse_name" label="仓库名称" />
      <el-table-column prop="current_quantity" label="当前库存" width="120" />
      <el-table-column prop="updated_at" label="更新时间" width="180" />
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
import { getInventoryBalances } from '@/api/inventory'
import type { InventoryBalance } from '@/types'

const list = ref<InventoryBalance[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const productId = ref<number | undefined>(undefined)
const warehouseId = ref<number | undefined>(undefined)

async function load() {
  loading.value = true
  try {
    const res = await getInventoryBalances({
      product_id: productId.value,
      warehouse_id: warehouseId.value,
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
