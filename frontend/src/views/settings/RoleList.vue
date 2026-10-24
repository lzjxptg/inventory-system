<template>
  <div class="page">
    <div class="page-header">
      <h3>角色管理</h3>
      <el-button type="primary" @click="openCreate" v-permission="'role:manage'">新建角色</el-button>
    </div>

    <el-table :data="roles" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="角色编码" width="160" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button
            size="small"
            :disabled="isBuiltin(row)"
            :title="isBuiltin(row) ? '系统内置角色不可修改角色编码' : ''"
            @click="openEdit(row)"
          >编辑</el-button>
          <el-button size="small" type="warning" @click="openPermission(row)">分配权限</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="isBuiltin(row)"
            :title="isBuiltin(row) ? '系统内置角色不可删除' : ''"
            @click="handleDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑角色 -->
    <el-dialog v-model="roleDialogVisible" :title="editingId ? '编辑角色' : '新建角色'" width="420px">
      <el-form :model="roleForm" label-width="80px">
        <el-form-item label="角色编码">
          <el-input
            v-model="roleForm.name"
            placeholder="如 admin"
            :disabled="isBuiltinByName(roleForm.name)"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分配权限 -->
    <el-dialog v-model="permDialogVisible" title="分配权限" width="560px">
      <div v-if="currentRole" class="perm-info">
        当前角色：<b>{{ currentRole.name }}</b>（{{ currentRole.description }}）
      </div>
      <el-tree
        ref="permTreeRef"
        :data="permTree"
        show-checkbox
        node-key="id"
        :default-checked-keys="checkedPermIds"
        :props="{ label: 'name', children: 'children' }"
      />
      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePermissions">保存权限</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getRoles,
  createRole,
  updateRole,
  deleteRole,
  getPermissions,
  getRolePermissionIds,
  assignRolePermissions,
} from '@/api/role'
import type { Role, Permission } from '@/types'

const roles = ref<Role[]>([])
const allPermissions = ref<Permission[]>([])

// 系统内置角色编码，不可修改编码、不可删除
const BUILTIN_ROLE_NAMES = ['admin', 'operator']

const isBuiltin = (row: Role): boolean => BUILTIN_ROLE_NAMES.includes(row.name)
const isBuiltinByName = (name: string): boolean => BUILTIN_ROLE_NAMES.includes(name)

const roleDialogVisible = ref(false)
const editingId = ref<number | null>(null)
const roleForm = ref({ name: '', description: '' })

const permDialogVisible = ref(false)
const currentRole = ref<Role | null>(null)
const checkedPermIds = ref<number[]>([])
const permTreeRef = ref()

// 按 module 分组构造树
const permTree = computed(() => {
  const groups: Record<string, Permission[]> = {}
  for (const p of allPermissions.value) {
    ;(groups[p.module] ||= []).push(p)
  }
  return Object.entries(groups).map(([module, list]) => ({
    id: `module-${module}`,
    name: module,
    children: list,
  }))
})

async function loadRoles() {
  const res = await getRoles()
  roles.value = res.data || []
}

async function loadPermissions() {
  const res = await getPermissions()
  allPermissions.value = res.data || []
}

function openCreate() {
  editingId.value = null
  roleForm.value = { name: '', description: '' }
  roleDialogVisible.value = true
}

function openEdit(row: Role) {
  editingId.value = row.id
  roleForm.value = { name: row.name, description: row.description }
  roleDialogVisible.value = true
}

async function saveRole() {
  if (!roleForm.value.name) {
    ElMessage.warning('请输入角色编码')
    return
  }
  try {
    if (editingId.value) {
      await updateRole(editingId.value, roleForm.value)
      ElMessage.success('更新成功')
    } else {
      await createRole(roleForm.value)
      ElMessage.success('创建成功')
    }
    roleDialogVisible.value = false
    loadRoles()
  } catch {
    /* 错误已由拦截器提示 */
  }
}

async function handleDelete(row: Role) {
  await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await deleteRole(row.id)
    ElMessage.success('删除成功')
    loadRoles()
  } catch {
    /* 拦截器已提示 */
  }
}

async function openPermission(row: Role) {
  currentRole.value = row
  const res = await getRolePermissionIds(row.id)
  checkedPermIds.value = res.data || []
  permDialogVisible.value = true
}

async function savePermissions() {
  if (!currentRole.value) return
  const checked = permTreeRef.value?.getCheckedKeys(true) as number[]
  const halfChecked = permTreeRef.value?.getHalfCheckedKeys() as number[]
  // 只保存叶子权限（真实 permission id，非 module 节点）
  const leafIds = [...checked, ...halfChecked].filter(
    (id) => typeof id === 'number',
  )
  try {
    await assignRolePermissions(currentRole.value.id, leafIds)
    ElMessage.success('权限分配成功')
    permDialogVisible.value = false
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(() => {
  loadRoles()
  loadPermissions()
})
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
.perm-info {
  margin-bottom: 12px;
}
</style>
