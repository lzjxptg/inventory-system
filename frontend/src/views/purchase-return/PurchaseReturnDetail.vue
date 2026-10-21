<template>
  <el-card v-loading="loading">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>采购退货单详情</span>
        <el-button @click="$router.back()">返回</el-button>
      </div>
    </template>

    <el-descriptions :column="2" border v-if="detail">
      <el-descriptions-item label="退货单号">{{ detail.return_no }}</el-descriptions-item>
      <el-descriptions-item label="状态">
        <el-tag :type="statusTag(detail.status)">{{ detail.status }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="原采购单号">{{ detail.order_no }}</el-descriptions-item>
      <el-descriptions-item label="供应商">{{ detail.supplier_name }}</el-descriptions-item>
      <el-descriptions-item label="仓库">{{ detail.warehouse_name }}</el-descriptions-item>
      <el-descriptions-item label="总数量">{{ detail.total_quantity }}</el-descriptions-item>
      <el-descriptions-item label="总金额">{{ detail.total_amount }}</el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
      <el-descriptions-item label="审核时间">{{ detail.approved_at || '-' }}</el-descriptions-item>
      <el-descriptions-item label="退货原因" :span="2">{{ detail.reason || '-' }}</el-descriptions-item>
    </el-descriptions>

    <el-table :data="detail?.items || []" border style="margin-top: 16px">
      <el-table-column prop="product_id" label="商品ID" width="80" />
      <el-table-column prop="product_name" label="商品名称" />
      <el-table-column prop="quantity" label="退货数量" width="120" />
      <el-table-column prop="unit_price" label="单价" width="120" />
      <el-table-column prop="amount" label="金额" width="140" />
      <el-table-column prop="batch_no" label="批次号" show-overflow-tooltip />
    </el-table>

    <el-form-item style="margin-top: 24px" v-if="detail">
      <el-button
        v-if="detail.status === 'draft'"
        type="warning"
        @click="$router.push(`/purchase-returns/edit/${detail.id}`)"
      >编辑</el-button>
      <el-button
        v-if="detail.status === 'draft'"
        type="primary"
        @click="handleSubmit"
      >提交审核</el-button>
      <el-button
        v-if="detail.status === 'submitted' && authStore.hasRole(['admin'])"
        type="success"
        @click="handleApprove"
      >审核通过</el-button>
      <el-button
        v-if="detail.status === 'submitted' && authStore.hasRole(['admin'])"
        type="danger"
        @click="handleReject"
      >驳回</el-button>
    </el-form-item>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getPurchaseReturn,
  submitPurchaseReturn,
  approvePurchaseReturn,
  rejectPurchaseReturn,
} from '@/api/purchaseReturn'
import type { PurchaseReturn } from '@/types'

const route = useRoute()
const authStore = useAuthStore()
const loading = ref(false)
const detail = ref<PurchaseReturn | null>(null)

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
    const res = await getPurchaseReturn(Number(route.params.id))
    detail.value = res.data
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!detail.value) return
  await ElMessageBox.confirm(`确认提交采购退货单「${detail.value.return_no}」审核？`, '提示', { type: 'warning' })
  try {
    await submitPurchaseReturn(detail.value.id)
    ElMessage.success('提交成功')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleApprove() {
  if (!detail.value) return
  await ElMessageBox.confirm(`确认审核通过采购退货单「${detail.value.return_no}」？审核通过后库存将回滚入库。`, '提示', { type: 'warning' })
  try {
    await approvePurchaseReturn(detail.value.id)
    ElMessage.success('审核通过')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleReject() {
  if (!detail.value) return
  await ElMessageBox.confirm(`确认驳回采购退货单「${detail.value.return_no}」？`, '提示', { type: 'warning' })
  try {
    await rejectPurchaseReturn(detail.value.id)
    ElMessage.success('已驳回')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(load)
</script>
