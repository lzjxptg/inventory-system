<template>
  <el-card>
    <template #header>新建销售订单</template>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="客户" prop="customer_id">
            <el-select
              v-model="form.customer_id"
              placeholder="请选择客户"
              filterable
              style="width: 100%"
              @change="onCustomerChange"
            >
              <el-option
                v-for="c in customers"
                :key="c.id"
                :label="c.name"
                :value="c.id"
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
          <el-form-item label="收货门店">
            <el-select
              v-model="form.shop_id"
              placeholder="可选，不选则不指定门店"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="s in shops"
                :key="s.id"
                :label="s.shop_name + (s.is_default === 1 ? '（默认）' : '')"
                :value="s.id"
              />
            </el-select>
            <div v-if="selectedShop && selectedShop.address" style="font-size: 12px; color: #909399; margin-top: 4px">
              收货地址：{{ selectedShop.address }}
            </div>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
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
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { createSalesOrder } from '@/api/sales'
import { getCustomers } from '@/api/customer'
import { getWarehouses } from '@/api/warehouse'
import { getProducts } from '@/api/product'
import { getCustomerShops } from '@/api/customerShop'
import type { SalesOrderCreate, Customer, Warehouse, Product, CustomerShop } from '@/types'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)

const customers = ref<Customer[]>([])
const warehouses = ref<Warehouse[]>([])
const products = ref<Product[]>([])
const shops = ref<CustomerShop[]>([])

const form = reactive<SalesOrderCreate>({
  customer_id: 0,
  warehouse_id: 0,
  shop_id: null,
  remark: '',
  items: [{ product_id: 0, quantity: 1, unit_price: 0 }],
})

const selectedShop = computed(
  () => shops.value.find((s) => s.id === form.shop_id) || null,
)

const rules: FormRules = {
  customer_id: [{ required: true, message: '请选择客户', trigger: 'change' }],
  warehouse_id: [{ required: true, message: '请选择仓库', trigger: 'change' }],
}

async function loadShops(customerId: number) {
  if (!customerId) {
    shops.value = []
    form.shop_id = null
    return
  }
  const res = await getCustomerShops(customerId)
  shops.value = res.data || []
  // 默认选中该客户的默认门店
  const def = shops.value.find((s) => s.is_default === 1)
  form.shop_id = def ? def.id : null
}

function onCustomerChange(customerId: number) {
  loadShops(customerId)
}

function addItem() {
  form.items.push({ product_id: 0, quantity: 1, unit_price: 0 })
}

function removeItem(index: number) {
  form.items.splice(index, 1)
}

async function loadOptions() {
  const [cRes, wRes, pRes] = await Promise.all([
    getCustomers({ skip: 0, limit: 1000 }),
    getWarehouses({ skip: 0, limit: 1000 }),
    getProducts({ skip: 0, limit: 1000 }),
  ])
  customers.value = cRes.data || []
  warehouses.value = wRes.data || []
  products.value = pRes.data || []
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    if (form.items.length === 0) {
      ElMessage.warning('至少添加一条明细')
      return
    }
    submitting.value = true
    try {
      await createSalesOrder({
        customer_id: form.customer_id,
        warehouse_id: form.warehouse_id,
        shop_id: form.shop_id || null,
        remark: form.remark || undefined,
        items: form.items.map((i) => ({
          product_id: i.product_id,
          quantity: i.quantity,
          unit_price: i.unit_price,
        })),
      })
      ElMessage.success('销售订单创建成功')
      router.push('/sales')
    } finally {
      submitting.value = false
    }
  })
}

onMounted(loadOptions)
</script>
