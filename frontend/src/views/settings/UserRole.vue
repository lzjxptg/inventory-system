<template>
  <div class="page">
    <div class="page-header">
      <h3>用户管理</h3>
      <div>
        <el-button type="primary" @click="openCreate">新建用户</el-button>
        <el-button @click="loadData">刷新</el-button>
      </div>
    </div>

    <el-alert
      title="说明：新建用户需设置密码（至少 6 位），角色默认为 operator。内置管理员受保护，不可删除最后一个管理员，也不能删除自己。"
      type="info"
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-table :data="users" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="200" />
      <el-table-column label="角色" width="160">
        <template #default="{ row }">
          <el-tag :type="row.role_id ? 'success' : 'info'">
            {{ roleName(row.role_id) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="200" />
      <el-table-column label="操作" min-width="360" fixed="right">
        <template #default="{ row }">
          <el-select
            v-model="assignMap[row.id]"
            placeholder="选择角色"
            style="width: 130px; margin-right: 8px"
            @change="() => handleAssign(row)"
          >
            <el-option
              v-for="r in roles"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </el-select>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="isSelf(row) || isLastAdmin(row)"
            :title="deleteTip(row)"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑用户弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑用户' : '新建用户'"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="登录账号" maxlength="50" />
        </el-form-item>
        <el-form-item
          :label="editingId ? '新密码' : '密码'"
          :prop="editingId ? undefined : 'password'"
        >
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="editingId ? '留空则不修改密码' : '至少 6 位'"
            show-password
            maxlength="128"
          />
        </el-form-item>
        <el-form-item
          v-if="!editingId"
          label="确认密码"
          prop="confirmPassword"
        >
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="再次输入密码"
            show-password
            maxlength="128"
          />
        </el-form-item>
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="form.role_id" placeholder="默认 operator" style="width: 100%">
            <el-option
              v-for="r in roles"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ editingId ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  getUsers,
  getRoles,
  assignUserRole,
  createUser,
  updateUser,
  deleteUser,
  countUsersByRole,
} from '@/api/role'
import type { User, Role } from '@/types'

const authStore = useAuthStore()

const users = ref<User[]>([])
const roles = ref<Role[]>([])
const assignMap = reactive<Record<number, number>>({})
const adminCount = ref(0)

// admin 角色的 id（从角色列表中查找 name === 'admin'）
const adminRoleId = computed<number | null>(() => {
  const r = roles.value.find((x) => x.name === 'admin')
  return r ? r.id : null
})

// 是否是当前登录用户自己
const isSelf = (row: User): boolean => row.id === authStore.user?.id

// 是否是系统内最后一个管理员
const isLastAdmin = (row: User): boolean => {
  if (!adminRoleId.value) return false
  return row.role_id === adminRoleId.value && adminCount.value <= 1
}

// 删除按钮 hover 提示
const deleteTip = (row: User): string => {
  if (isSelf(row)) return '不能删除当前登录账号'
  if (isLastAdmin(row)) return '当前为唯一管理员，无法删除。请先为其他用户分配管理员角色后再操作'
  return ''
}

// ---------------- 新建/编辑用户 ----------------
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  role_id: null as number | null,
})

const validateConfirmPassword = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) {
    callback(new Error('请再次输入密码'))
  } else if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { max: 50, message: '用户名不超过 50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度 6-128 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

function openCreate() {
  editingId.value = null
  form.username = ''
  form.password = ''
  form.confirmPassword = ''
  form.role_id = null
  dialogVisible.value = true
}

function openEdit(row: User) {
  editingId.value = row.id
  form.username = row.username
  form.password = ''
  form.confirmPassword = ''
  form.role_id = row.role_id ?? null
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  // 编辑模式下密码非必填，仅在填写时校验长度
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  // 编辑模式：若填写了密码则校验长度
  if (editingId.value && form.password && (form.password.length < 6 || form.password.length > 128)) {
    ElMessage.warning('密码长度需为 6-128 位')
    return
  }

  submitting.value = true
  try {
    if (editingId.value) {
      const payload: { username: string; role_id: number | null; password?: string } = {
        username: form.username,
        role_id: form.role_id || null,
      }
      if (form.password) payload.password = form.password
      await updateUser(editingId.value, payload)
      ElMessage.success('用户更新成功')
    } else {
      await createUser({
        username: form.username,
        password: form.password,
        role_id: form.role_id || null,
      })
      ElMessage.success('用户创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch {
    /* 拦截器已提示 */
  } finally {
    submitting.value = false
  }
}

// ---------------- 删除用户 ----------------
async function handleDelete(row: User) {
  if (isSelf(row) || isLastAdmin(row)) return
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username}」吗？此操作不可恢复`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.msg || e?.response?.data?.msg || '删除失败')
    }
  }
}

function roleName(roleId: number | null | undefined): string {
  if (!roleId) return 'operator (默认)'
  const r = roles.value.find((x) => x.id === roleId)
  return r ? r.name : 'operator (默认)'
}

async function loadData() {
  const [uRes, rRes] = await Promise.all([getUsers(), getRoles()])
  users.value = uRes.data || []
  roles.value = rRes.data || []
  // 回填当前角色
  for (const u of users.value) {
    if (u.role_id) assignMap[u.id] = u.role_id
  }
  // 刷新 admin 用户总数
  try {
    const cntRes = await countUsersByRole('admin')
    adminCount.value = cntRes.data?.count ?? 0
  } catch {
    adminCount.value = 0
  }
}

async function handleAssign(row: User) {
  const roleId = assignMap[row.id]
  if (!roleId) return
  try {
    await assignUserRole(row.id, roleId)
    ElMessage.success(`已将 ${row.username} 的角色更新为「${roleName(roleId)}」`)
    loadData()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(loadData)
</script>

<style scoped>
.page {
  background: #fff;
  padding: 16px;
  border-radius: 4px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
</style>
