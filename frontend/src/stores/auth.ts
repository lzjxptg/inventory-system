import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi } from '@/api/auth'
import { getMyPermissions, getCurrentUserInfo } from '@/api/role'
import { ElMessage } from 'element-plus'
import {
  getToken,
  setToken,
  removeToken,
  getUserInfo,
  setUserInfo,
  removeUserInfo,
  decodeJwtPayload,
} from '@/utils/auth'
import type { User } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<User | null>(getUserInfo())
  const permissions = ref<string[]>([])

  async function fetchPermissions(): Promise<void> {
    try {
      const res = await getMyPermissions()
      permissions.value = res.data || []
    } catch {
      permissions.value = []
    }
  }

  async function login(username: string, password: string): Promise<boolean> {
    try {
      const res = await loginApi({ username, password })
      if (res.access_token) {
        token.value = res.access_token
        setToken(res.access_token)
        // 从 JWT 载荷解析用户名与角色
        const payload = decodeJwtPayload(res.access_token)
        // 拉取完整用户信息（含 id），避免仅靠 JWT 中的 sub(username) 缺失主键
        let u: User
        try {
          const meRes = await getCurrentUserInfo()
          u = {
            id: meRes.data.id,
            username: meRes.data.username,
            role: meRes.data.role || payload?.role || 'operator',
          }
        } catch {
          u = {
            id: 0,
            username: payload?.sub || username,
            role: payload?.role || 'operator',
          }
        }
        user.value = u
        setUserInfo(u)
        // 登录后立即获取当前用户权限 code 列表
        await fetchPermissions()
        ElMessage.success('登录成功')
        return true
      }
      return false
    } catch {
      return false
    }
  }

  function logout(): void {
    token.value = ''
    user.value = null
    permissions.value = []
    removeToken()
    removeUserInfo()
    window.location.href = '/login'
  }

  function hasPermission(code: string | string[]): boolean {
    if (!permissions.value.length) return false
    return Array.isArray(code)
      ? code.some((c) => permissions.value.includes(c))
      : permissions.value.includes(code)
  }

  function hasRole(roles: string[] | undefined): boolean {
    if (!roles || !roles.length) return true
    return !!user.value?.role && roles.includes(user.value.role)
  }

  return { token, user, permissions, login, logout, fetchPermissions, hasPermission, hasRole }
})
