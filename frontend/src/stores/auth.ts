import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi } from '@/api/auth'
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

  async function login(username: string, password: string): Promise<boolean> {
    try {
      const res = await loginApi({ username, password })
      if (res.access_token) {
        token.value = res.access_token
        // 后端登录接口不返回 user 信息，从 JWT 载荷中解析用户名
        const payload = decodeJwtPayload(res.access_token)
        const u: User = { id: 0, username: payload?.sub || username }
        user.value = u
        setToken(res.access_token)
        setUserInfo(u)
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
    removeToken()
    removeUserInfo()
    window.location.href = '/login'
  }

  return { token, user, login, logout }
})
