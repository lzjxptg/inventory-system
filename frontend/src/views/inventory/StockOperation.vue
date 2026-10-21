<template>
  <div>
    <el-tabs v-model="activeTab" class="op-tabs">
      <el-tab-pane label="手动入库" name="in">
        <el-card>
          <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" style="max-width: 600px">
            <el-form-item label="商品" prop="product_id">
              <el-select v-model="form.product_id" placeholder="请选择商品" filterable style="width: 100%">
                <el-option
                  v-for="p in products"
                  :key="p.id"
                  :label="`${p.name}（${p.sku}）`"
                  :value="p.id"
                />
              </el-select>
            </el-form-item>
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
            <el-form-item label="入库数量" prop="quantity">
              <el-input-number v-model="form.quantity" :min="0.01" :precision="2" :step="1" style="width: 100%" />
            </el-form-item>
            <el-form-item label="关联类型">
              <el-select v-model="form.reference_type" placeholder="无" clearable style="width: 100%">
                <el-option label="采购入库" value="PURCHASE" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="备注信息" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="handleSubmit">确认入库</el-button>
              <el-button @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="手动出库" name="out">
        <el-card>
          <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" style="max-width: 600px">
            <el-form-item label="商品" prop="product_id">
              <el-select v-model="form.product_id" placeholder="请选择商品" filterable style="width: 100%">
                <el-option
                  v-for="p in products"
                  :key="p.id"
                  :label="`${p.name}（${p.sku}）`"
                  :value="p.id"
                />
              </el-select>
            </el-form-item>
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
            <el-form-item label="出库数量" prop="quantity">
              <el-input-number v-model="form.quantity" :min="0.01" :precision="2" :step="1" style="width: 100%" />
              <div class="form-tip">出库时后端会校验库存是否充足</div>
            </el-form-item>
            <el-form-item label="关联类型">
              <el-select v-model="form.reference_type" placeholder="无" clearable style="width: 100%">
                <el-option label="销售出库" value="SALE" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="备注信息" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="handleSubmit">确认出库</el-button>
              <el-button @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { stockIn, stockOut } from '@/api/inventory'
import { getProducts } from '@/api/product'
import { getWarehouses } from '@/api/warehouse'
import type { Product, Warehouse, StockMovementCreate } from '@/types'

const activeTab = ref<'in' | 'out'>('in')
const products = ref<Product[]>([])
const warehouses = ref<Warehouse[]>([])
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = ref<StockMovementCreate>({
  product_id: 0,
  warehouse_id: 0,
  quantity: 1,
  reference_type: undefined,
  remark: '',
})

const rules: FormRules = {
  product_id: [{ required: true, message: '请选择商品', trigger: 'change' }],
  warehouse_id: [{ required: true, message: '请选择仓库', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
}

async function loadOptions() {
  const [pRes, wRes] = await Promise.all([
    getProducts({ skip: 0, limit: 1000 }),
    getWarehouses({ skip: 0, limit: 1000 }),
  ])
  products.value = pRes.data || []
  warehouses.value = wRes.data || []
}

function resetForm() {
  form.value = {
    product_id: 0,
    warehouse_id: 0,
    quantity: 1,
    reference_type: undefined,
    remark: '',
  }
  formRef.value?.resetFields()
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload: StockMovementCreate = {
        product_id: form.value.product_id,
        warehouse_id: form.value.warehouse_id,
        quantity: form.value.quantity,
        reference_type: form.value.reference_type || undefined,
        remark: form.value.remark || undefined,
      }
      if (activeTab.value === 'in') {
        await stockIn(payload)
        ElMessage.success('入库成功')
      } else {
        await stockOut(payload)
        ElMessage.success('出库成功')
      }
      resetForm()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.msg || e?.response?.data?.detail || e?.message || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

onMounted(loadOptions)
</script>

<style scoped>
.op-tabs {
  margin-bottom: 16px;
}
.form-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>
