<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="客户名称">
        <el-input v-model="keyword" placeholder="客户名称" clearable />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="success" v-permission="'sales:view'" @click="openCreate">新增客户</el-button>
        <el-button type="warning" v-permission="'sales:view'" :loading="exporting" @click="handleExport">导出 Excel</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="contact" label="联系人" width="120" />
      <el-table-column prop="phone" label="电话" width="140" />
      <el-table-column prop="address" label="地址" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="primary" @click="openShops(row)">门店</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
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

    <!-- 新增/编辑客户弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑客户' : '新增客户'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" placeholder="如 C001" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="客户名称" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact" placeholder="联系人姓名" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" type="textarea" :rows="2" placeholder="地址" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 门店管理弹窗 -->
    <el-dialog
      v-model="shopsVisible"
      :title="`门店管理 - ${currentCustomer?.name || ''}`"
      width="720px"
      :close-on-click-modal="false"
    >
      <div style="margin-bottom: 12px">
        <el-button type="primary" @click="openShopCreate">+ 新增门店</el-button>
      </div>
      <el-table :data="shops" v-loading="shopsLoading" stripe border>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="shop_name" label="门店名称" min-width="120" />
        <el-table-column prop="contact" label="联系人" width="100" />
        <el-table-column prop="phone" label="电话" width="130" />
        <el-table-column prop="address" label="收货地址" min-width="180" show-overflow-tooltip />
        <el-table-column label="默认" width="70">
          <template #default="{ row }">
            <el-tag v-if="row.is_default === 1" type="success">默认</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openShopEdit(row)">编辑</el-button>
            <el-button size="small" type="warning" @click="handleSetDefault(row)" :disabled="row.is_default === 1">设默认</el-button>
            <el-button size="small" type="danger" @click="handleDeleteShop(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新增/编辑门店子弹窗 -->
      <el-dialog
        v-model="shopDialogVisible"
        :title="shopEditingId ? '编辑门店' : '新增门店'"
        width="480px"
        append-to-body
      >
        <el-form ref="shopFormRef" :model="shopForm" :rules="shopRules" label-width="80px">
          <el-form-item label="门店名" prop="shop_name">
            <el-input v-model="shopForm.shop_name" placeholder="门店名称" />
          </el-form-item>
          <el-form-item label="联系人">
            <el-input v-model="shopForm.contact" placeholder="联系人" />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="shopForm.phone" placeholder="电话" />
          </el-form-item>
          <el-form-item label="地址">
            <el-input v-model="shopForm.address" type="textarea" :rows="2" placeholder="收货地址" />
          </el-form-item>
          <el-form-item label="设默认">
            <el-switch v-model="shopForm.is_default" :active-value="1" :inactive-value="0" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="shopDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="shopSubmitting" @click="handleShopSubmit">保存</el-button>
        </template>
      </el-dialog>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getCustomers,
  createCustomer,
  updateCustomer,
  deleteCustomer,
  exportCustomers,
} from '@/api/customer'
import { downloadBlob } from '@/utils/download'
import {
  getCustomerShops,
  createCustomerShop,
  updateCustomerShop,
  deleteCustomerShop,
  setDefaultShop,
} from '@/api/customerShop'
import type { Customer, CustomerShop, CustomerShopCreate } from '@/types'

const list = ref<Customer[]>([])
const loading = ref(false)
const exporting = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const keyword = ref('')

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = ref({
  code: '',
  name: '',
  contact: '',
  phone: '',
  address: '',
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入客户编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入客户名称', trigger: 'blur' }],
}

// ---------------- 门店管理 ----------------
const shopsVisible = ref(false)
const shopsLoading = ref(false)
const shops = ref<CustomerShop[]>([])
const currentCustomer = ref<Customer | null>(null)

const shopDialogVisible = ref(false)
const shopEditingId = ref<number | null>(null)
const shopSubmitting = ref(false)
const shopFormRef = ref<FormInstance>()
const shopForm = ref<CustomerShopCreate>({
  customer_id: 0,
  shop_name: '',
  contact: '',
  phone: '',
  address: '',
  is_default: 0,
})
const shopRules: FormRules = {
  shop_name: [{ required: true, message: '请输入门店名称', trigger: 'blur' }],
}

async function loadShops(customerId: number) {
  shopsLoading.value = true
  try {
    const res = await getCustomerShops(customerId)
    shops.value = res.data || []
  } finally {
    shopsLoading.value = false
  }
}

function openShops(row: Customer) {
  currentCustomer.value = row
  shopsVisible.value = true
  loadShops(row.id)
}

function openShopCreate() {
  if (!currentCustomer.value) return
  shopEditingId.value = null
  shopForm.value = {
    customer_id: currentCustomer.value.id,
    shop_name: '',
    contact: '',
    phone: '',
    address: '',
    is_default: 0,
  }
  shopDialogVisible.value = true
}

function openShopEdit(row: CustomerShop) {
  shopEditingId.value = row.id
  shopForm.value = {
    customer_id: row.customer_id,
    shop_name: row.shop_name,
    contact: row.contact || '',
    phone: row.phone || '',
    address: row.address || '',
    is_default: row.is_default || 0,
  }
  shopDialogVisible.value = true
}

async function handleShopSubmit() {
  if (!shopFormRef.value) return
  await shopFormRef.value.validate(async (valid) => {
    if (!valid) return
    shopSubmitting.value = true
    try {
      const payload: CustomerShopCreate = {
        customer_id: shopForm.value.customer_id,
        shop_name: shopForm.value.shop_name,
        contact: shopForm.value.contact || null,
        phone: shopForm.value.phone || null,
        address: shopForm.value.address || null,
        is_default: shopForm.value.is_default || 0,
      }
      if (shopEditingId.value) {
        await updateCustomerShop(shopEditingId.value, payload)
        ElMessage.success('门店更新成功')
      } else {
        await createCustomerShop(payload)
        ElMessage.success('门店创建成功')
      }
      shopDialogVisible.value = false
      if (currentCustomer.value) loadShops(currentCustomer.value.id)
    } finally {
      shopSubmitting.value = false
    }
  })
}

async function handleSetDefault(row: CustomerShop) {
  try {
    await setDefaultShop(row.id)
    ElMessage.success('已设为默认门店')
    if (currentCustomer.value) loadShops(currentCustomer.value.id)
  } catch {
    /* 拦截器已提示 */
  }
}

async function handleDeleteShop(row: CustomerShop) {
  await ElMessageBox.confirm(`确认删除门店「${row.shop_name}」？`, '提示', { type: 'warning' })
  try {
    await deleteCustomerShop(row.id)
    ElMessage.success('删除成功')
    if (currentCustomer.value) loadShops(currentCustomer.value.id)
  } catch {
    /* 拦截器已提示 */
  }
}

async function load() {
  loading.value = true
  try {
    const res = await getCustomers({
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    let data = res.data || []
    if (keyword.value) {
      data = data.filter((c) => c.name.includes(keyword.value))
    }
    list.value = data
    total.value = data.length
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  load()
}

function handleReset() {
  keyword.value = ''
  page.value = 1
  load()
}

async function handleExport() {
  exporting.value = true
  try {
    const blob = await exportCustomers({
      keyword: keyword.value || undefined,
    } as any)
    const date = new Date().toISOString().slice(0, 10)
    downloadBlob(blob, `客户列表_${date}.xlsx`)
  } catch {
    ElMessage.error('导出失败（后端接口待实现）')
  } finally {
    exporting.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { code: '', name: '', contact: '', phone: '', address: '' }
  dialogVisible.value = true
}

function openEdit(row: Customer) {
  editingId.value = row.id
  form.value = {
    code: row.code,
    name: row.name,
    contact: row.contact || '',
    phone: row.phone || '',
    address: row.address || '',
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        code: form.value.code,
        name: form.value.name,
        contact: form.value.contact || null,
        phone: form.value.phone || null,
        address: form.value.address || null,
      }
      if (editingId.value) {
        await updateCustomer(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createCustomer(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      load()
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: Customer) {
  await ElMessageBox.confirm(`确认删除客户「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await deleteCustomer(row.id)
    ElMessage.success('删除成功')
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
