import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getToken } from '@/utils/auth'
import { useAuthStore } from '@/stores/auth'

const Layout = () => import('@/components/Layout.vue')

// 扩展 meta 类型
declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    roles?: string[]
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'inventory',
        name: 'StockList',
        component: () => import('@/views/inventory/StockList.vue'),
        meta: { title: '库存列表' },
      },
      {
        path: 'inventory/movements',
        name: 'StockMovement',
        component: () => import('@/views/inventory/StockMovement.vue'),
        meta: { title: '库存流水' },
      },
      {
        path: 'products',
        name: 'ProductList',
        component: () => import('@/views/product/ProductList.vue'),
        meta: { title: '商品管理' },
      },
      {
        path: 'warehouses',
        name: 'WarehouseList',
        component: () => import('@/views/warehouse/WarehouseList.vue'),
        meta: { title: '仓库管理' },
      },
      {
        path: 'purchase',
        name: 'PurchaseOrders',
        component: () => import('@/views/purchase/PurchaseOrders.vue'),
        meta: { title: '采购订单' },
      },
      {
        path: 'purchase/create',
        name: 'PurchaseCreate',
        component: () => import('@/views/purchase/PurchaseCreate.vue'),
        meta: { title: '新建采购' },
      },
      {
        path: 'sales',
        name: 'SalesOrders',
        component: () => import('@/views/sales/SalesOrders.vue'),
        meta: { title: '销售订单' },
      },
      {
        path: 'sales/create',
        name: 'SalesCreate',
        component: () => import('@/views/sales/SalesCreate.vue'),
        meta: { title: '新建销售' },
      },
      {
        path: 'reports/inventory-movements',
        name: 'InventoryMovementsReport',
        component: () => import('@/views/reports/InventoryMovements.vue'),
        meta: { title: '流水汇总' },
      },
      {
        path: 'reports/low-stock',
        name: 'LowStockAlerts',
        component: () => import('@/views/reports/LowStockAlerts.vue'),
        meta: { title: '低库存预警' },
      },
      {
        path: 'reports/purchase',
        name: 'PurchaseSummary',
        component: () => import('@/views/reports/PurchaseSummary.vue'),
        meta: { title: '采购统计' },
      },
      {
        path: 'reports/sales',
        name: 'SalesSummary',
        component: () => import('@/views/reports/SalesSummary.vue'),
        meta: { title: '销售统计' },
      },
      {
        path: 'settings/roles',
        name: 'RoleList',
        component: () => import('@/views/settings/RoleList.vue'),
        meta: { title: '角色管理', roles: ['admin'] },
      },
      {
        path: 'settings/user-role',
        name: 'UserRole',
        component: () => import('@/views/settings/UserRole.vue'),
        meta: { title: '用户角色', roles: ['admin'] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局守卫
router.beforeEach(async (to, _from, next) => {
  const token = getToken()
  if (to.meta.requiresAuth === false) {
    if (to.path === '/login' && token) {
      next('/')
    } else {
      next()
    }
    return
  }
  // 受保护路由：未登录跳登录页
  if (!token) {
    next('/login')
    return
  }
  const auth = useAuthStore()
  // 页面刷新后 permissions 为空，需重新拉取
  if (!auth.permissions.length) {
    await auth.fetchPermissions()
  }
  // 角色守卫：若路由配置了 meta.roles，当前用户角色不在白名单则拒绝
  if (to.meta.roles && to.meta.roles.length) {
    const role = auth.user?.role || 'operator'
    if (!to.meta.roles.includes(role)) {
      ElMessage.warning('无权限访问该页面')
      next('/dashboard')
      return
    }
  }
  next()
})

export default router
