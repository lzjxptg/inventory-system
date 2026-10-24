import request from './request'
import type { Role, Permission, User } from '@/types'

export interface UserCreatePayload {
  username: string
  password: string
  role_id?: number | null
}

// 角色列表
export function getRoles() {
  return request.get<unknown, { code: number; data: Role[] }>('/roles')
}

// 新建角色
export function createRole(data: { name: string; description?: string }) {
  return request.post('/roles', data)
}

// 更新角色
export function updateRole(id: number, data: { name?: string; description?: string }) {
  return request.put(`/roles/${id}`, data)
}

// 删除角色
export function deleteRole(id: number) {
  return request.delete(`/roles/${id}`)
}

// 全部权限列表
export function getPermissions() {
  return request.get<unknown, { code: number; data: Permission[] }>('/permissions')
}

// 查询角色已分配权限 ID 列表
export function getRolePermissionIds(roleId: number) {
  return request.get<unknown, { code: number; data: number[] }>(`/roles/${roleId}/permissions`)
}

// 分配角色权限（全量覆盖）
export function assignRolePermissions(roleId: number, permissionIds: number[]) {
  return request.put(`/roles/${roleId}/permissions`, { permission_ids: permissionIds })
}

// 当前用户信息（含 role）
export function getCurrentUserInfo() {
  return request.get<unknown, { code: number; data: User }>('/roles/me')
}

// 当前用户权限 code 列表
export function getMyPermissions() {
  return request.get<unknown, { code: number; data: string[] }>('/roles/me/permissions')
}

// 用户列表
export function getUsers() {
  return request.get<unknown, { code: number; data: User[] }>('/users')
}

// 分配用户角色
export function assignUserRole(userId: number, roleId: number) {
  return request.put(`/users/${userId}/role`, { role_id: roleId })
}

// 创建用户（仅 admin）
export function createUser(data: UserCreatePayload) {
  return request.post('/users', data)
}

// 编辑用户（仅 admin，可更新用户名/角色/密码）
export function updateUser(
  id: number,
  data: { username?: string; password?: string; role_id?: number | null },
) {
  return request.put(`/users/${id}`, data)
}

// 删除用户（仅 admin）
export function deleteUser(id: number) {
  return request.delete(`/users/${id}`)
}

// 统计指定角色的启用用户数量（仅 admin）
export function countUsersByRole(roleKey: string) {
  return request.get<unknown, { code: number; data: { role_key: string; count: number } }>(
    '/users/count-by-role',
    { params: { role_key: roleKey } },
  )
}
