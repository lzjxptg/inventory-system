<template>
  <div>
    <el-form :inline="true" class="filter-form">
      <el-form-item label="商品名称">
        <el-input v-model="keyword" placeholder="商品名称" clearable />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="categoryId" placeholder="全部分类" clearable style="width: 160px">
          <el-option
            v-for="c in categories"
            :key="c.id"
            :label="c.name"
            :value="c.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
        <el-button type="success" v-permission="'inventory:view'" @click="openCreate">新增商品</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="list" v-loading="loading" stripe border>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="sku" label="编码" width="120" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="spec" label="规格" width="120" />
      <el-table-column label="分类" width="120">
        <template #default="{ row }">
          {{ categoryName(row.category_id) }}
        </template>
      </el-table-column>
      <el-table-column label="单位" width="80">
        <template #default="{ row }">
          {{ unitName(row.unit_id) }}
        </template>
      </el-table-column>
      <el-table-column prop="purchase_price" label="成本价" width="100" />
      <el-table-column prop="sale_price" label="销售价" width="100" />
      <el-table-column prop="min_stock" label="预警阈值" width="100" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'">
            {{ row.status === 1 ? '上架' : '下架' }}
          </el-tag>
        </template>
      </el-table-column>
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

    <!-- 新增/编辑商品弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑商品' : '新增商品'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="90px"
      >
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="商品编码" prop="sku">
              <el-input v-model="form.sku" placeholder="如 P001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="商品名称" prop="name">
              <el-input v-model="form.name" placeholder="商品名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="分类">
              <el-select v-model="form.category_id" placeholder="请选择分类" clearable style="width: 100%">
                <el-option
                  v-for="c in categories"
                  :key="c.id"
                  :label="c.name"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位" prop="unit_id">
              <el-select v-model="form.unit_id" placeholder="请选择单位" style="width: 100%">
                <el-option
                  v-for="u in units"
                  :key="u.id"
                  :label="u.name"
                  :value="u.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="规格">
              <el-input v-model="form.spec" placeholder="规格型号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch
                v-model="form.status"
                :active-value="1"
                :inactive-value="0"
                active-text="上架"
                inactive-text="下架"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="成本价">
              <el-input-number
                v-model="form.purchase_price"
                :min="0"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="销售价">
              <el-input-number
                v-model="form.sale_price"
                :min="0"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="预警阈值">
              <el-input-number
                v-model="form.min_stock"
                :min="0"
                :precision="3"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
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
  getProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  getCategories,
  getUnits,
} from '@/api/product'
import type { Product, Category, Unit } from '@/types'

const list = ref<Product[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const keyword = ref('')
const categoryId = ref<number | undefined>(undefined)

const categories = ref<Category[]>([])
const units = ref<Unit[]>([])

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = ref({
  sku: '',
  name: '',
  category_id: undefined as number | undefined,
  unit_id: undefined as number | undefined,
  spec: '',
  purchase_price: 0,
  sale_price: 0,
  min_stock: 0,
  status: 1,
})

const rules: FormRules = {
  sku: [{ required: true, message: '请输入商品编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  unit_id: [{ required: true, message: '请选择单位', trigger: 'change' }],
}

function categoryName(id: number | null): string {
  if (!id) return '-'
  const c = categories.value.find((x) => x.id === id)
  return c ? c.name : String(id)
}

function unitName(id: number): string {
  const u = units.value.find((x) => x.id === id)
  return u ? u.name : String(id)
}

async function load() {
  loading.value = true
  try {
    const res = await getProducts({
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    let data = res.data || []
    // 前端按名称/分类筛选（后端列表接口暂无 name/category 过滤参数）
    if (keyword.value) {
      data = data.filter((p) => p.name.includes(keyword.value))
    }
    if (categoryId.value) {
      data = data.filter((p) => p.category_id === categoryId.value)
    }
    list.value = data
    total.value = data.length
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [cRes, uRes] = await Promise.all([getCategories(), getUnits()])
  categories.value = cRes.data || []
  units.value = uRes.data || []
}

function handleSearch() {
  page.value = 1
  load()
}

function handleReset() {
  keyword.value = ''
  categoryId.value = undefined
  page.value = 1
  load()
}

function openCreate() {
  editingId.value = null
  form.value = {
    sku: '',
    name: '',
    category_id: undefined,
    unit_id: undefined,
    spec: '',
    purchase_price: 0,
    sale_price: 0,
    min_stock: 0,
    status: 1,
  }
  dialogVisible.value = true
}

function openEdit(row: Product) {
  editingId.value = row.id
  form.value = {
    sku: row.sku,
    name: row.name,
    category_id: row.category_id ?? undefined,
    unit_id: row.unit_id,
    spec: row.spec || '',
    purchase_price: Number(row.purchase_price),
    sale_price: Number(row.sale_price),
    min_stock: Number(row.min_stock),
    status: row.status,
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
        sku: form.value.sku,
        name: form.value.name,
        category_id: form.value.category_id ?? null,
        unit_id: form.value.unit_id!,
        spec: form.value.spec || null,
        purchase_price: form.value.purchase_price,
        sale_price: form.value.sale_price,
        min_stock: form.value.min_stock,
        status: form.value.status,
      }
      if (editingId.value) {
        await updateProduct(editingId.value, payload)
        ElMessage.success('更新成功')
      } else {
        await createProduct(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      load()
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: Product) {
  await ElMessageBox.confirm(`确认删除商品「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await deleteProduct(row.id)
    ElMessage.success('删除成功')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(() => {
  loadOptions()
  load()
})
</script>

<style scoped>
.filter-form {
  margin-bottom: 16px;
}
</style>
