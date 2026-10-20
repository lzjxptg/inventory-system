<template>
  <div class="page">
    <div class="page-header">
      <h3>用户角色分配</h3>
      <el-button type="primary" @click="loadData">刷新</el-button>
    </div>

    <el-table :data="users" border stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="用户名" width="200" />
      <el-table-column label="当前角色" width="200">
        <template #default="{ row }">
          <el-tag :type="row.role ? 'success' : 'info'">
            {{ row.role || 'operator (默认)' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { getUsers, getRoles, assignUserRole } from '@/api/role'
import type { User, Role } from '@/types'

const users = ref<User[]>([])
const roles = ref<Role[]>([])
const assignMap = reactive<Record<number, number>>({})

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
    ElMessage.success(`已将 ${row.username} 的角色更新`)
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
