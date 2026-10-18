import axios from 'axios'
import type { LoginRequest, LoginResponse, ApiResponse, User } from '@/types'
import request from './request'

/**
 * 登录接口走 axios 直连，绕过 request.ts 的统一响应包装。
 * 后端 OAuth2PasswordRequestForm 要求 application/x-www-form-urlencoded，
 * 成功后直接返回 { access_token, token_type }（非 {code,msg,data} 结构）。
 */
export function login(data: LoginRequest): Promise<LoginResponse> {
  const params = new URLSearchParams()
  params.append('username', data.username)
  params.append('password', data.password)
  return axios
    .post('/api/v1/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    .then((res) => res.data as LoginResponse)
}

export function register(data: { username: string; password: string }): Promise<ApiResponse<User>> {
  return request.post('/auth/register', data)
}
