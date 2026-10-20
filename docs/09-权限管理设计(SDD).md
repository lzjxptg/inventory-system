# 权限管理设计文档 (SDD)

版本：v1.0
日期：2026-10-20
模块：RBAC 权限管理

## 1. 设计概述

### 1.1 背景

- 系统已有用户体系（`users` 表 + JWT 鉴权），但所有登录用户权限相同，无法区分管理员与普通操作员。
- 新增 RBAC（Role-Based Access Control）权限模型，通过「角色 → 权限」关联，用户绑定单一角色，实现菜单、按钮、接口三级权限控制。

### 1.2 目标

- 后端：基于 JWT payload 中的 `role` 字段做接口级鉴权依赖注入。
- 前端：路由 `meta.roles` 守卫 + 菜单按角色动态渲染 + `v-permission` 按钮级指令。
- 预置两个角色：`admin`（全部权限）、`operator`（查看 + 创建，无删除/配置权限）。

### 1.3 约束

- 不破坏现有 118 个测试；现有业务页面不动，仅追加角色管理页面。
- 端口不变：后端 8002，前端 3000。
- 登录接口仍返回 OAuth2 标准格式 `{access_token, token_type}`，`role` 写入 JWT payload。

## 2. 数据模型

### 2.1 roles（角色表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BigInteger PK | 主键 |
| name | String(50) unique | 角色编码，如 admin / operator |
| description | String(255) | 角色描述 |
| is_deleted | TINYINT | 逻辑删除 |
| created_at | DateTime | 创建时间 |

### 2.2 permissions（权限表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BigInteger PK | 主键 |
| code | String(100) unique | 权限编码，如 `role:manage`、`purchase:create` |
| name | String(100) | 权限名称 |
| module | String(50) | 所属模块，如 settings / purchase / sales / inventory / reports |
| is_deleted | TINYINT | 逻辑删除 |
| created_at | DateTime | 创建时间 |

### 2.3 role_permissions（角色-权限关联表）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | BigInteger PK | 主键 |
| role_id | BigInteger FK → roles.id | 角色ID |
| permission_id | BigInteger FK → permissions.id | 权限ID |
| created_at | DateTime | 创建时间 |

唯一约束：`(role_id, permission_id)`。

### 2.4 users 表追加 role_id

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| role_id | BigInteger FK → roles.id, nullable | 用户角色ID，NULL 表示无角色（默认 operator） |

通过 Alembic 生成 migration 文件（`alembic revision --autogenerate`）执行表结构变更，新增 `roles`、`permissions`、`role_permissions` 三张表，并为 `users` 表追加 `role_id` 外键列。

## 3. 后端设计

### 3.1 文件结构

```
models/role.py          # Role / Permission / RolePermission ORM
schemas/role.py         # RoleCreate/Update/Response、PermissionOut、RolePermissionAssign
crud/role.py            # 角色/权限 CRUD + 分配
core/permissions.py     # require_role / require_permission 依赖
routers/roles.py        # /api/v1/roles 路由
```

### 3.2 角色 CRUD 接口（`/api/v1/roles`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/v1/roles | 角色列表 |
| POST | /api/v1/roles | 新建角色（name 唯一校验） |
| PUT | /api/v1/roles/{id} | 更新角色 |
| DELETE | /api/v1/roles/{id} | 逻辑删除角色 |
| GET | /api/v1/permissions | 全部权限列表（按 module 分组） |
| GET | /api/v1/roles/{id}/permissions | 查询角色已分配权限 ID 列表 |
| PUT | /api/v1/roles/{id}/permissions | 分配权限（body: {permission_ids: [...]}） |
| GET | /api/v1/roles/me | 返回当前登录用户信息（含 role） |
| GET | /api/v1/roles/me/permissions | 返回当前用户权限 code 列表 |
| PUT | /api/v1/users/{id}/role | 分配用户角色（body: {role_id: int}） |

### 3.3 鉴权依赖（`core/permissions.py`）

- `require_role(*roles: str)`：JWT payload 中 `role` 不在白名单 → 40301 禁止访问。
- `require_permission(perm_code: str)`：查询用户角色拥有的权限列表，不包含 `perm_code` → 40301。
- `get_current_user` 不变，但登录时 JWT payload 追加 `role` 字段（角色 name）。
- `users.role_id` 为 NULL 时，默认按 `operator` 角色处理。

### 3.4 登录 JWT

`create_access_token(data={"sub": user.username, "role": role_name})`，前端解码 JWT 取 `role`。

## 4. 前端设计

### 4.1 文件结构

```
src/api/role.ts                 # 角色/权限 API
src/utils/permission.ts         # v-permission 自定义指令
src/views/settings/RoleList.vue # 角色管理 + 权限分配
src/views/settings/UserRole.vue # 用户角色分配
```

修改：`router/index.ts`（`meta.roles`）、`components/Layout.vue`（菜单过滤）、`stores/auth.ts`（存 role）、`main.ts`（注册指令）、`types/index.ts`（Role/Permission 类型）。

### 4.2 路由 meta.roles

每个受保护路由 `meta.roles: string[]`，未配置则所有登录用户可访问。
`router.beforeEach` 中：若 `to.meta.roles` 存在且不包含当前用户 role → 跳转 `/dashboard` 并提示无权限。

### 4.3 菜单动态渲染

Layout 中菜单数据带 `roles` 字段，`v-if="hasRole(item.roles)"` 过滤。
`settings` 菜单仅 `admin` 可见。

### 4.4 v-permission 指令

```ts
app.directive('permission', {
  mounted(el, binding) {
    const perms = authStore.permissions  // 当前用户权限 code 列表
    const needed = binding.value  // string | string[]
    const ok = Array.isArray(needed) ? needed.some(p => perms.includes(p)) : perms.includes(needed)
    if (!ok) el.parentNode?.removeChild(el)
  }
})
```

### 4.5 stores/auth

登录后的完整流程：**登录 → 从 JWT 解码 `role` → 调用 `/api/v1/roles/me/permissions` 获取权限 code 列表 → 存入 store**。

- `login` 后从 JWT 解码 `role`，存入 `user.role`。
- 新增 `permissions` 状态（`string[]`），登录成功后立即调用 `/api/v1/roles/me/permissions` 获取当前用户权限 code 列表并持久化。
- `v-permission` 指令与菜单过滤均读取 `authStore.permissions`。

## 5. 预置数据

- 权限表预置权限点：
  - settings 模块：`role:manage`、`user:role`
  - purchase 模块：`purchase:view`、`purchase:create`、`purchase:delete`
  - sales 模块：`sales:view`、`sales:create`、`sales:delete`
  - inventory 模块：`inventory:view`、`inventory:in`、`inventory:out`
  - reports 模块：`reports:view`
- 角色：
  - `admin`：全部权限
  - `operator`：所有 `:view`、`:create`、`:in`、`:out` 权限，不含 `:delete`、`role:manage`、`user:role`
- `admin` 用户绑定 `admin` 角色；新注册用户默认 `operator`。
- `frontend_test` 用户 `role_id` 设为 `operator`（用于前端 operator 角色验收）。

## 6. 权限矩阵

| 操作 | admin | operator |
| --- | --- | --- |
| 查看所有页面 | ✅ | ✅ |
| 创建采购/销售单 | ✅ | ✅ |
| 删除采购/销售单 | ✅ | ❌ |
| 角色管理 | ✅ | ❌ |
| 分配用户角色 | ✅ | ❌ |

## 7. 非功能需求

- 鉴权依赖不产生额外 N+1 查询：`require_permission` 可缓存用户权限到请求上下文。
- 前端 `v-permission` 仅隐藏入口，后端接口仍强制校验，防止越权。
