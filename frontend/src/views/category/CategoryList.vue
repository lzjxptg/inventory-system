<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item>
        <el-button type="success" v-permission="'inventory:view'" @click="openCreate">新增分类</el-button>
        <el-button @click="loadTree">刷新</el-button>
      </el-form-item>
    </el-form>

    <el-table
      :data="treeData"
      v-loading="loading"
      stripe
      border
      row-key="id"
      :tree-props="{ children: 'children' }"
      default-expand-all
    >
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="分类名称" min-width="180" />
      <el-table-column prop="sort" label="排序" width="80" />
      <el-table-column label="父分类" width="120">
        <template #default="{ row }">
          {{ parentName(row.parent_id) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑分类' : '新增分类'" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入分类名称" />
        </el-form-item>
        <el-form-item label="父分类" prop="parent_id">
          <el-select v-model="form.parent_id" placeholder="顶级分类（不选）" clearable style="width: 100%">
            <el-option
              v-for="c in flatList"
              :key="c.id"
              :label="c.name"
              :value="c.id"
              :disabled="isEdit && c.id === editingId"
            />
          </el-select>
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
  getCategoryTree,
  getCategories,
  createCategory,
  updateCategory,
  deleteCategory,
} from '@/api/category'
import type { Category, CategoryTreeNode, CategoryCreate, CategoryUpdate } from '@/types'

const treeData = ref<CategoryTreeNode[]>([])
const flatList = ref<Category[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = ref<CategoryCreate & CategoryUpdate>({
  name: '',
  parent_id: null,
  sort: 0,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
}

async function loadTree() {
  loading.value = true
  try {
    const res = await getCategoryTree()
    treeData.value = res.data || []
  } finally {
    loading.value = false
  }
}

async function loadFlat() {
  const res = await getCategories({ skip: 0, limit: 1000 })
  flatList.value = res.data || []
}

function parentName(parentId: number | null): string {
  if (parentId === null || parentId === undefined) return '顶级'
  const p = flatList.value.find((x) => x.id === parentId)
  return p ? p.name : '顶级'
}

function openCreate() {
  isEdit.value = false
  editingId.value = null
  form.value = { name: '', parent_id: null, sort: 0 }
  dialogVisible.value = true
}

function openEdit(row: CategoryTreeNode) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    parent_id: row.parent_id,
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
      const payload: CategoryCreate = {
        name: form.value.name!,
        parent_id: form.value.parent_id ?? null,
        sort: form.value.sort ?? 0,
      }
      if (isEdit.value && editingId.value) {
        await updateCategory(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createCategory(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      await Promise.all([loadTree(), loadFlat()])
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.msg || e?.message || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: CategoryTreeNode) {
  try {
    await ElMessageBox.confirm(
      `确定删除分类「${row.name}」吗？如有子分类或关联商品将删除失败。`,
      '删除确认',
      { type: 'warning' }
    )
    await deleteCategory(row.id)
    ElMessage.success('删除成功')
    await Promise.all([loadTree(), loadFlat()])
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || e?.message || '删除失败')
    }
  }
}

onMounted(() => {
  loadTree()
  loadFlat()
})
</script>
