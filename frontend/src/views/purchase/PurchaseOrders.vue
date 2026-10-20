<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="状态">
        <el-select v-model="status" placeholder="全部" clearable style="width: 120px">
          <el-option label="草稿" value="draft" />
          <el-option label="已提交" value="submitted" />
          <el-option label="已审核" value="approved" />
          <el-option label="已完成" value="completed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item label="供应商ID">
        <el-input v-model.number="supplierId" placeholder="供应商ID" clearable />
      </el-form-item>
      <el-form-item label="关键字">
        <el-input v-model="keyword" placeholder="订单号/备注" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="success" @click="$router.push('/purchase/create')">新建采购</el-button>
        <el-button type="warning" v-permission="'purchase:view'" @click="handleExport">导出 Excel</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="order_no" label="订单号" width="160" />
      <el-table-column prop="supplier_name" label="供应商" />
      <el-table-column prop="warehouse_name" label="仓库" width="120" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_quantity" label="总数量" width="100" />
      <el-table-column prop="total_amount" label="总金额" width="120" />
      <el-table-column prop="remark" label="备注" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="180" />
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
import { getPurchaseOrders, exportPurchaseOrders } from '@/api/purchase'
import { downloadBlob } from '@/utils/download'
import type { PurchaseOrder } from '@/types'

const list = ref<PurchaseOrder[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const status = ref<string | undefined>(undefined)
const supplierId = ref<number | undefined>(undefined)
const keyword = ref('')

function statusTag(s: string): string {
  const map: Record<string, string> = {
    draft: 'info',
    submitted: 'warning',
    approved: 'primary',
    completed: 'success',
    cancelled: 'danger',
  }
  return map[s] || 'info'
}

async function load() {
  loading.value = true
  try {
    const res = await getPurchaseOrders({
      status: status.value,
      supplier_id: supplierId.value,
      keyword: keyword.value || undefined,
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
  status.value = undefined
  supplierId.value = undefined
  keyword.value = ''
  page.value = 1
  load()
}

async function handleExport() {
  try {
    const blob = await exportPurchaseOrders({
      status: status.value,
      supplier_id: supplierId.value,
      keyword: keyword.value || undefined,
    })
    downloadBlob(blob, `采购订单_${Date.now()}.xlsx`)
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
