<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="状态">
        <el-select v-model="status" placeholder="全部" clearable style="width: 120px">
          <el-option label="草稿" value="draft" />
          <el-option label="已提交" value="submitted" />
          <el-option label="已审核" value="approved" />
          <el-option label="已驳回" value="rejected" />
        </el-select>
      </el-form-item>
      <el-form-item label="客户ID">
        <el-input v-model.number="customerId" placeholder="客户ID" clearable />
      </el-form-item>
      <el-form-item label="关键字">
        <el-input v-model="keyword" placeholder="退货单号/原因" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="success" @click="$router.push('/sales-returns/create')">新建退货</el-button>
        <el-button type="warning" v-permission="'sales_return:view'" @click="handleExport">导出 Excel</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="return_no" label="退货单号" width="180" />
      <el-table-column prop="order_no" label="原销售单号" width="160" />
      <el-table-column prop="customer_name" label="客户" />
      <el-table-column prop="warehouse_name" label="仓库" width="120" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_quantity" label="总数量" width="100" />
      <el-table-column prop="total_amount" label="总金额" width="120" />
      <el-table-column prop="reason" label="退货原因" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="320" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'draft'"
            size="small"
            type="primary"
            @click="$router.push(`/sales-returns/edit/${row.id}`)"
          >编辑</el-button>
          <el-button
            v-if="row.status === 'draft'"
            size="small"
            type="danger"
            @click="handleDelete(row)"
          >删除</el-button>
          <el-button
            v-if="row.status === 'draft'"
            size="small"
            type="warning"
            @click="handleSubmit(row)"
          >提交</el-button>
          <el-button
            v-if="row.status === 'submitted' && authStore.hasRole(['admin'])"
            size="small"
            type="success"
            @click="handleApprove(row)"
          >审核</el-button>
          <el-button
            v-if="row.status === 'submitted' && authStore.hasRole(['admin'])"
            size="small"
            type="info"
            @click="handleReject(row)"
          >驳回</el-button>
        </template>
      </el-table-column>
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

    <el-dialog v-model="detailVisible" title="销售退货单详情" width="800px">
      <el-descriptions :column="2" border v-if="detail">
        <el-descriptions-item label="退货单号">{{ detail.return_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(detail.status)">{{ detail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="原销售单号">{{ detail.order_no }}</el-descriptions-item>
        <el-descriptions-item label="客户">{{ detail.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ detail.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="总数量">{{ detail.total_quantity }}</el-descriptions-item>
        <el-descriptions-item label="总金额">{{ detail.total_amount }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="退货原因" :span="2">{{ detail.reason || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="detail?.items || []" border style="margin-top: 16px">
        <el-table-column prop="product_id" label="商品ID" width="80" />
        <el-table-column prop="product_name" label="商品名称" />
        <el-table-column prop="quantity" label="退货数量" width="100" />
        <el-table-column prop="unit_price" label="单价" width="100" />
        <el-table-column prop="amount" label="金额" width="120" />
        <el-table-column prop="batch_no" label="批次号" show-overflow-tooltip />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getSalesReturns,
  exportSalesReturns,
  getSalesReturn,
  deleteSalesReturn,
  submitSalesReturn,
  approveSalesReturn,
  rejectSalesReturn,
} from '@/api/saleReturn'
import { downloadBlob } from '@/utils/download'
import type { SalesReturn } from '@/types'

const authStore = useAuthStore()
const list = ref<SalesReturn[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const status = ref<string | undefined>(undefined)
const customerId = ref<number | undefined>(undefined)
const keyword = ref('')

const detailVisible = ref(false)
const detail = ref<SalesReturn | null>(null)

function statusTag(s: string): string {
  const map: Record<string, string> = {
    draft: 'info',
    submitted: 'warning',
    approved: 'primary',
    rejected: 'danger',
  }
  return map[s] || 'info'
}

async function load() {
  loading.value = true
  try {
    const res = await getSalesReturns({
      status: status.value,
      customer_id: customerId.value,
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
  customerId.value = undefined
  keyword.value = ''
  page.value = 1
  load()
}

async function handleExport() {
  try {
    const blob = await exportSalesReturns({
      status: status.value,
      customer_id: customerId.value,
      keyword: keyword.value || undefined,
    })
    downloadBlob(blob, `销售退货单_${Date.now()}.xlsx`)
  } catch {
    ElMessage.error('导出失败')
  }
}

async function openDetail(row: SalesReturn) {
  const res = await getSalesReturn(row.id)
  detail.value = res.data
  detailVisible.value = true
}

async function handleDelete(row: SalesReturn) {
  await ElMessageBox.confirm(`确认删除销售退货单「${row.return_no}」？仅草稿状态可删除。`, '提示', { type: 'warning' })
  try {
    await deleteSalesReturn(row.id)
    ElMessage.success('删除成功')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleSubmit(row: SalesReturn) {
  await ElMessageBox.confirm(`确认提交销售退货单「${row.return_no}」审核？`, '提示', { type: 'warning' })
  try {
    await submitSalesReturn(row.id)
    ElMessage.success('提交成功')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleApprove(row: SalesReturn) {
  await ElMessageBox.confirm(`确认审核通过销售退货单「${row.return_no}」？审核通过后库存将扣减。`, '提示', { type: 'warning' })
  try {
    await approveSalesReturn(row.id)
    ElMessage.success('审核通过')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleReject(row: SalesReturn) {
  await ElMessageBox.confirm(`确认驳回销售退货单「${row.return_no}」？`, '提示', { type: 'warning' })
  try {
    await rejectSalesReturn(row.id)
    ElMessage.success('已驳回')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(load)
</script>

<style scoped>
.filter-form {
  margin-bottom: 16px;
}
</style>
