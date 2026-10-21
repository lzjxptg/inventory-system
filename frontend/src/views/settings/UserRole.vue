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
      title="说明：新建用户需设置密码（至少 6 位），角色默认为 operator。删除/重置密码接口由后端提供。"
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
      <el-table-column label="操作" min-width="280">
        <template #default="{ row }">
          <el-select
            v-model="assignMap[row.id]"
            placeholder="选择角色"
            style="width: 160px"
            @change="() => handleAssign(row)"
          >
            <el-option
              v-for="r in roles"
              :key="r.id"
              :label="r.name"
              :value="r.id"
            />
          </el-select>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建用户弹窗 -->
    <el-dialog
      v-model="createVisible"
      title="新建用户"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="登录账号" maxlength="50" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="createForm.password"
            type="password"
            placeholder="至少 6 位"
            show-password
            maxlength="128"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="createForm.confirmPassword"
            type="password"
            placeholder="再次输入密码"
            show-password
            maxlength="128"
          />
        </el-form-item>
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="createForm.role_id" placeholder="默认 operator" style="width: 100%">
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
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { getUsers, getRoles, assignUserRole, createUser } from '@/api/role'
import type { User, Role } from '@/types'

const users = ref<User[]>([])
const roles = ref<Role[]>([])
const assignMap = reactive<Record<number, number>>({})

// ---------------- 新建用户 ----------------
const createVisible = ref(false)
const creating = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  role_id: null as number | null,
})

const validateConfirmPassword = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  if (!value) {
    callback(new Error('请再次输入密码'))
  } else if (value !== createForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const createRules: FormRules = {
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
  createForm.username = ''
  createForm.password = ''
  createForm.confirmPassword = ''
  createForm.role_id = null
  createVisible.value = true
}

async function handleCreate() {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    creating.value = true
    try {
      await createUser({
        username: createForm.username,
        password: createForm.password,
        role_id: createForm.role_id || null,
      })
      ElMessage.success('用户创建成功')
      createVisible.value = false
      loadData()
    } catch {
      /* 拦截器已提示 */
    } finally {
      creating.value = false
    }
  })
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
