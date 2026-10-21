<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item>
        <el-button type="success" v-permission="'inventory:view'" @click="openCreate">新增单位</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" width="120" />
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="sort" label="排序" width="80" />
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑单位' : '新增单位'" width="450px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：个、箱、件" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" placeholder="单位编码（可选）" />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" :max="9999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  getUnits,
  createUnit,
  updateUnit,
  deleteUnit,
} from '@/api/unit'
import type { Unit, UnitCreate, UnitUpdate } from '@/types'

const list = ref<Unit[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = ref<UnitCreate & UnitUpdate>({
  name: '',
  code: '',
  sort: 0,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入单位名称', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    const res = await getUnits({ skip: 0, limit: 1000 })
    list.value = res.data || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = { name: '', code: '', sort: 0 }
  dialogVisible.value = true
}

function openEdit(row: Unit) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    code: row.code ?? '',
    sort: row.sort,
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload: UnitCreate = {
        name: form.value.name!,
        code: form.value.code || undefined,
        sort: form.value.sort ?? 0,
      }
      if (isEdit.value && editingId.value) {
        await updateUnit(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createUnit(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      await load()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.msg || e?.message || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: Unit) {
  try {
    await ElMessageBox.confirm(
      `确定删除单位「${row.name}」吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await deleteUnit(row.id)
    ElMessage.success('删除成功')
    await load()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || e?.message || '删除失败')
    }
  }
}

onMounted(load)
</script>
