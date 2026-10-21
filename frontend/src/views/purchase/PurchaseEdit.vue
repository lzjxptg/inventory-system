<template>
  <el-card v-loading="loading">
    <template #header>编辑采购订单</template>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="供应商" prop="supplier_id">
            <el-select v-model="form.supplier_id" placeholder="请选择供应商" filterable style="width: 100%">
              <el-option
                v-for="s in suppliers"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="仓库" prop="warehouse_id">
            <el-select v-model="form.warehouse_id" placeholder="请选择仓库" style="width: 100%">
              <el-option
                v-for="w in warehouses"
                :key="w.id"
                :label="w.name"
                :value="w.id"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="备注">
            <el-input v-model="form.remark" placeholder="可选" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-divider content-position="left">订单明细</el-divider>

      <el-table :data="form.items" border>
        <el-table-column label="商品" min-width="200">
          <template #default="{ row }">
            <el-select v-model="row.product_id" placeholder="请选择商品" filterable style="width: 100%">
              <el-option
                v-for="p in products"
                :key="p.id"
                :label="`${p.name}（${p.sku}）`"
                :value="p.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="160">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="0.01" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="单价" width="160">
          <template #default="{ row }">
            <el-input-number v-model="row.unit_price" :min="0" :precision="2" style="width: 100%" />
          </template>
        </el-table-column>
        <el-table-column label="金额" width="140">
          <template #default="{ row }">
            {{ (Number(row.quantity || 0) * Number(row.unit_price || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ $index }">
            <el-button type="danger" link @click="removeItem($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-button style="margin-top: 12px" @click="addItem">+ 添加明细</el-button>

      <el-form-item style="margin-top: 24px">
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getPurchaseOrder, updatePurchaseOrder } from '@/api/purchase'
import { getSuppliers } from '@/api/supplier'
import { getWarehouses } from '@/api/warehouse'
import { getProducts } from '@/api/product'
import type { PurchaseOrderCreate, Supplier, Warehouse, Product } from '@/types'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)

const suppliers = ref<Supplier[]>([])
const warehouses = ref<Warehouse[]>([])
const products = ref<Product[]>([])

const form = reactive<PurchaseOrderCreate>({
  supplier_id: 0,
  warehouse_id: 0,
  remark: '',
  items: [{ product_id: 0, quantity: 1, unit_price: 0 }],
})

const rules: FormRules = {
  supplier_id: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  warehouse_id: [{ required: true, message: '请选择仓库', trigger: 'change' }],
}

function addItem() {
  form.items.push({ product_id: 0, quantity: 1, unit_price: 0 })
}

function removeItem(index: number) {
  form.items.splice(index, 1)
}

async function loadOptions() {
  const [sRes, wRes, pRes] = await Promise.all([
    getSuppliers({ skip: 0, limit: 1000 }),
    getWarehouses({ skip: 0, limit: 1000 }),
    getProducts({ skip: 0, limit: 1000 }),
  ])
  suppliers.value = sRes.data || []
  warehouses.value = wRes.data || []
  products.value = pRes.data || []
}

async function loadOrder() {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    const res = await getPurchaseOrder(id)
    const order = res.data
    form.supplier_id = order.supplier_id
    form.warehouse_id = order.warehouse_id
    form.remark = order.remark || ''
    form.items = (order.items || []).map((it: any) => ({
      product_id: it.product_id,
      quantity: Number(it.quantity),
      unit_price: Number(it.unit_price),
    }))
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    if (form.items.length === 0) {
      ElMessage.warning('至少添加一条明细')
      return
    }
    const id = Number(route.params.id)
    submitting.value = true
    try {
      await updatePurchaseOrder(id, {
        supplier_id: form.supplier_id,
        warehouse_id: form.warehouse_id,
        remark: form.remark || undefined,
        items: form.items.map((i) => ({
          product_id: i.product_id,
          quantity: i.quantity,
          unit_price: i.unit_price,
        })),
      })
      ElMessage.success('采购订单更新成功')
      router.push('/purchase')
    } finally {
      submitting.value = false
    }
  })
}

onMounted(() => {
  loadOptions()
  loadOrder()
})
</script>
