<template>
  <el-card>
    <template #header>{{ isEdit ? '编辑销售退货单' : '新建销售退货单' }}</template>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="原销售订单" prop="sales_order_id">
            <el-select
              v-model="form.sales_order_id"
              placeholder="请选择销售订单"
              filterable
              style="width: 100%"
              :disabled="isEdit"
              @change="onOrderChange"
            >
              <el-option
                v-for="o in orders"
                :key="o.id"
                :label="`${o.order_no}（${o.customer_name}）`"
                :value="o.id"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="客户">
            <el-input :value="currentOrder?.customer_name || '-'" disabled />
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="仓库">
            <el-input :value="currentOrder?.warehouse_name || '-'" disabled />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row>
        <el-col :span="24">
          <el-form-item label="退货原因">
            <el-input v-model="form.reason" type="textarea" :rows="2" placeholder="请输入退货原因" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">退货明细</el-divider>

      <el-table :data="form.items" border v-if="form.items.length">
        <el-table-column prop="product_name" label="商品名称" min-width="180" />
        <el-table-column label="已出库数量" width="120">
          <template #default="{ row }">{{ row.shipped_quantity }}</template>
        </el-table-column>
        <el-table-column label="退货数量" width="180">
          <template #default="{ row }">
            <el-input-number
              v-model="row.quantity"
              :min="0"
              :max="Number(row.shipped_quantity)"
              :precision="2"
              style="width: 100%"
            />
          </template>
        </el-table-column>
        <el-table-column label="退货单价" width="180">
          <template #default="{ row }">
            <el-input-number v-model="row.unit_price" :min="0" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="金额" width="140">
          <template #default="{ row }">
            {{ (Number(row.quantity || 0) * Number(row.unit_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="批次号" min-width="160">
          <template #default="{ row }">
            <el-input v-model="row.batch_no" placeholder="可选" />
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="请先选择销售订单" :image-size="80" />

      <el-form-item style="margin-top: 24px">
        <el-tag type="warning">退货总数量：{{ totalQuantity }}</el-tag>
        <el-tag type="success" style="margin-left: 12px">退货总金额：{{ totalAmount }}</el-tag>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getSalesOrders, getSalesOrder } from '@/api/sales'
import { createSalesReturn, updateSalesReturn, getSalesReturn } from '@/api/saleReturn'
import type { SalesReturnItemCreate } from '@/types'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)

const formRef = ref<FormInstance>()
const submitting = ref(false)
const orders = ref<any[]>([])
const currentOrder = ref<any>(null)

interface FormItem extends SalesReturnItemCreate {
  product_name?: string
  shipped_quantity?: number
}

const form = reactive<{
  sales_order_id: number | null
  reason: string
  items: FormItem[]
}>({
  sales_order_id: null,
  reason: '',
  items: [],
})

const rules: FormRules = {
  sales_order_id: [{ required: true, message: '请选择销售订单', trigger: 'change' }],
}

const totalQuantity = computed(() =>
  form.items.reduce((s, it) => s + Number(it.quantity || 0), 0).toFixed(2),
)
const totalAmount = computed(() =>
  form.items
    .reduce((s, it) => s + Number(it.quantity || 0) * Number(it.unit_price || 0), 0)
    .toFixed(2),
)

async function loadOrders() {
  const res = await getSalesOrders({ skip: 0, limit: 500 })
  orders.value = (res.data || []).filter((o: any) =>
    ['approved', 'partial_out', 'completed'].includes(o.status),
  )
}

async function onOrderChange(orderId: number) {
  if (!orderId) {
    currentOrder.value = null
    form.items = []
    return
  }
  const res = await getSalesOrder(orderId)
  currentOrder.value = res.data
  form.items = (res.data?.items || [])
    .filter((it: any) => Number(it.shipped_quantity || 0) > 0)
    .map((it: any) => ({
      product_id: it.product_id,
      product_name: it.product_name,
      shipped_quantity: Number(it.shipped_quantity),
      quantity: 0,
      unit_price: Number(it.unit_price),
      batch_no: null,
    }))
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!form.sales_order_id) {
    ElMessage.warning('请选择销售订单')
    return
  }
  const items = form.items.filter((it) => Number(it.quantity) > 0)
  if (!items.length) {
    ElMessage.warning('请填写退货数量')
    return
  }
  const payload = {
    sales_order_id: form.sales_order_id,
    reason: form.reason || undefined,
    items: items.map((it) => ({
      product_id: it.product_id,
      quantity: it.quantity,
      unit_price: it.unit_price,
      batch_no: it.batch_no || undefined,
    })),
  }
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateSalesReturn(Number(route.params.id), payload)
      ElMessage.success('修改成功')
    } else {
      await createSalesReturn(payload)
      ElMessage.success('创建成功')
    }
    router.push('/sales-returns')
  } finally {
    submitting.value = false
  }
}

async function loadExisting() {
  const id = Number(route.params.id)
  const res = await getSalesReturn(id)
  const data = res.data
  form.sales_order_id = data.sales_order_id
  form.reason = data.reason || ''
  currentOrder.value = {
    customer_name: data.customer_name,
    warehouse_name: data.warehouse_name,
  }
  const orderRes = await getSalesOrder(data.sales_order_id)
  const orderItems = orderRes.data?.items || []
  form.items = orderItems
    .filter((it: any) => Number(it.shipped_quantity || 0) > 0)
    .map((it: any) => {
      const ret = data.items.find((ri: any) => ri.product_id === it.product_id)
      return {
        product_id: it.product_id,
        product_name: it.product_name,
        shipped_quantity: Number(it.shipped_quantity),
        quantity: ret ? Number(ret.quantity) : 0,
        unit_price: ret ? Number(ret.unit_price) : Number(it.unit_price),
        batch_no: ret?.batch_no || null,
      }
    })
}

onMounted(async () => {
  await loadOrders()
  if (isEdit.value) {
    await loadExisting()
  }
})
</script>
