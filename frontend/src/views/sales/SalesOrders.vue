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
      <el-form-item label="客户ID">
        <el-input v-model.number="customerId" placeholder="客户ID" clearable />
      </el-form-item>
      <el-form-item label="关键字">
        <el-input v-model="keyword" placeholder="订单号/备注" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="success" @click="$router.push('/sales/create')">新建销售</el-button>
        <el-button type="warning" v-permission="'sales:view'" @click="handleExport">导出 Excel</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="order_no" label="订单号" width="160" />
      <el-table-column prop="customer_name" label="客户" />
      <el-table-column prop="warehouse_name" label="仓库" width="120" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_quantity" label="总数量" width="100" />
      <el-table-column prop="total_amount" label="总金额" width="120" />
      <el-table-column prop="remark" label="备注" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'draft'"
            size="small"
            type="primary"
            @click="$router.push(`/sales/edit/${row.id}`)"
          >编辑</el-button>
          <el-button
            v-if="row.status === 'draft'"
            size="small"
            type="warning"
            @click="handleSubmit(row)"
          >提交审核</el-button>
          <el-button
            v-if="row.status === 'draft'"
            size="small"
            type="danger"
            @click="handleDelete(row)"
          >删除</el-button>
          <el-button
            v-if="row.status === 'submitted' && authStore.hasRole(['admin'])"
            size="small"
            type="success"
            @click="handleApprove(row)"
          >审核</el-button>
          <!-- 打印为只读操作，跟随订单查看权限，不单独鉴权 -->
          <el-button
            v-if="row.status === 'approved'"
            size="small"
            type="primary"
            @click="openDetailPrint(row)"
          >打印</el-button>
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

    <!-- 订单详情弹窗 -->
    <el-dialog v-model="detailVisible" title="销售订单详情" width="800px">
      <el-descriptions :column="2" border v-if="detail">
        <el-descriptions-item label="订单号">{{ detail.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(detail.status)">{{ detail.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="客户">{{ detail.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="仓库">{{ detail.warehouse_name }}</el-descriptions-item>
        <el-descriptions-item label="送货门店">{{ detail.shop_name || '未指定' }}</el-descriptions-item>
        <el-descriptions-item label="门店地址">{{ detail.shop_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="总数量">{{ detail.total_quantity }}</el-descriptions-item>
        <el-descriptions-item label="总金额">{{ detail.total_amount }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ detail.remark || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ detail.updated_at }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="detail?.items || []" border style="margin-top: 16px">
        <el-table-column prop="product_sku" label="商品编码" width="120" />
        <el-table-column prop="product_name" label="商品名称" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="unit_price" label="单价" width="100" />
        <el-table-column prop="amount" label="金额" width="120" />
        <el-table-column prop="shipped_quantity" label="已出库" width="100" />
        <el-table-column prop="remark" label="备注" show-overflow-tooltip />
      </el-table>
      <template #footer>
        <!-- 打印为只读操作，跟随订单查看权限，不单独鉴权 -->
        <el-button v-if="detail?.status === 'approved'" type="primary" @click="openPrint">
          <el-icon><Printer /></el-icon> 打印
        </el-button>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 打印预览弹窗 -->
    <el-dialog v-model="printVisible" title="打印预览" width="900px" top="5vh">
      <PrintOrder v-if="detail" type="sales" :order="detail" />
      <template #footer>
        <el-button type="primary" @click="doPrint">打印</el-button>
        <el-button @click="printVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Printer } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import {
  getSalesOrders,
  exportSalesOrders,
  getSalesOrder,
  deleteSalesOrder,
  submitSalesOrder,
  approveSalesOrder,
} from '@/api/sales'
import { downloadBlob } from '@/utils/download'
import PrintOrder from '@/components/PrintOrder.vue'
import type { SalesOrder } from '@/types'

const authStore = useAuthStore()
const list = ref<SalesOrder[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const status = ref<string | undefined>(undefined)
const customerId = ref<number | undefined>(undefined)
const keyword = ref('')

const detailVisible = ref(false)
const detail = ref<SalesOrder | null>(null)
const printVisible = ref(false)

function openPrint() {
  printVisible.value = true
}

function doPrint() {
  nextTick(() => {
    window.print()
  })
}

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

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    draft: '草稿',
    submitted: '待审核',
    approved: '已审核',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[s] || s
}

async function load() {
  loading.value = true
  try {
    const res = await getSalesOrders({
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
    const blob = await exportSalesOrders({
      status: status.value,
      customer_id: customerId.value,
      keyword: keyword.value || undefined,
    })
    downloadBlob(blob, `销售订单_${Date.now()}.xlsx`)
  } catch {
    ElMessage.error('导出失败')
  }
}

async function openDetail(row: SalesOrder) {
  const res = await getSalesOrder(row.id)
  detail.value = res.data
  detailVisible.value = true
}

async function openDetailPrint(row: SalesOrder) {
  const res = await getSalesOrder(row.id)
  detail.value = res.data
  printVisible.value = true
}

async function handleDelete(row: SalesOrder) {
  await ElMessageBox.confirm(`确认删除销售订单「${row.order_no}」？仅草稿状态可删除。`, '提示', { type: 'warning' })
  try {
    await deleteSalesOrder(row.id)
    ElMessage.success('删除成功')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleSubmit(row: SalesOrder) {
  await ElMessageBox.confirm(`确认提交审核销售订单「${row.order_no}」？`, '提示', { type: 'warning' })
  try {
    await submitSalesOrder(row.id)
    ElMessage.success('提交审核成功')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleApprove(row: SalesOrder) {
  await ElMessageBox.confirm(`确认审核通过销售订单「${row.order_no}」？`, '提示', { type: 'warning' })
  try {
    await approveSalesOrder(row.id)
    ElMessage.success('审核通过')
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
