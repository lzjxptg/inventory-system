import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import { getToken, removeToken, removeUserInfo } from '@/utils/auth'
import type { ApiResponse } from '@/types'

const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// 请求拦截：自动携带 JWT
request.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截：统一处理业务码与 HTTP 错误
request.interceptors.response.use(
  (response: AxiosResponse<ApiResponse | any>) => {
    const res = response.data

    // 登录接口直接返回 { access_token, token_type }，不走统一包装
    if (res && typeof res === 'object' && 'access_token' in res) {
      return res
    }

    // 统一响应 { code, msg, data }
    if (res && typeof res === 'object' && 'code' in res) {
      if (res.code === 0 || res.code === 200) {
        return res
      }
      // 认证失败：后端以 HTTP 200 + code 40101 包装，需主动登出并跳转登录
      if (res.code === 40101) {
        removeToken()
        removeUserInfo()
        ElMessage.error(res.msg || '登录已过期，请重新登录')
        window.location.href = '/login'
        return Promise.reject(res)
      }
      ElMessage.error(res.msg || '请求失败')
      return Promise.reject(res)
    }

    // 兜底：无 code 字段，直接返回原始数据
    return res
  },
  (error) => {
    const status = error?.response?.status
    if (status === 401) {
      removeToken()
      removeUserInfo()
      ElMessage.error('登录已过期，请重新登录')
      window.location.href = '/login'
    } else if (error?.response?.data?.msg) {
      ElMessage.error(error.response.data.msg)
    } else if (error?.message?.includes('Network Error')) {
      ElMessage.error('网络异常，请稍后重试')
    } else {
      ElMessage.error(error?.message || '请求异常')
    }
    return Promise.reject(error)
  },
)

export default request
