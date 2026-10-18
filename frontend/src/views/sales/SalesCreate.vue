<template>
  <el-card>
    <template #header>新建销售订单</template>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="客户ID" prop="customer_id">
            <el-input-number v-model="form.customer_id" :min="1" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="仓库ID" prop="warehouse_id">
            <el-input-number v-model="form.warehouse_id" :min="1" style="width: 100%" />
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
        <el-table-column label="商品ID" width="160">
          <template #default="{ row }">
            <el-input-number v-model="row.product_id" :min="1" style="width: 100%" />
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
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { createSalesOrder } from '@/api/sales'
import type { SalesOrderCreate } from '@/types'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive<SalesOrderCreate>({
  customer_id: 1,
  warehouse_id: 1,
  remark: '',
  items: [{ product_id: 1, quantity: 1, unit_price: 0 }],
})

const rules: FormRules = {
  customer_id: [{ required: true, message: '请输入客户ID', trigger: 'blur' }],
  warehouse_id: [{ required: true, message: '请输入仓库ID', trigger: 'blur' }],
}

function addItem() {
  form.items.push({ product_id: 1, quantity: 1, unit_price: 0 })
}

function removeItem(index: number) {
  form.items.splice(index, 1)
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
</script>
