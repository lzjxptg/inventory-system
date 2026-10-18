import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { getToken } from '@/utils/auth'

const Layout = () => import('@/components/Layout.vue')

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
router.beforeEach((to, _from, next) => {
  const token = getToken()
  if (to.meta.requiresAuth === false) {
    // 登录页：已登录则跳首页
    if (to.path === '/login' && token) {
      next('/')
    } else {
      next()
    }
  } else {
    // 受保护路由：未登录跳登录页
    if (!token) {
      next('/login')
    } else {
      next()
    }
  }
})

export default router
