// token 存取与 JWT 载荷解析工具

const TOKEN_KEY = 'access_token'
const USER_KEY = 'user_info'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function getUserInfo(): any {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? JSON.parse(raw) : null
}

export function setUserInfo(user: any): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function removeUserInfo(): void {
  localStorage.removeItem(USER_KEY)
}

/**
 * 解码 JWT 载荷（不验签，仅用于前端读取用户名等非敏感信息）。
 */
export function decodeJwtPayload(token: string): any {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const decoded = decodeURIComponent(
      atob(payload)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    )
    return JSON.parse(decoded)
  } catch {
    return null
  }
}
