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
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
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
import type { Customer } from '@/types'

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
