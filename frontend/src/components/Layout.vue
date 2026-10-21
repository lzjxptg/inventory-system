<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="layout-aside">
      <div class="logo">进销存管理</div>
      <el-menu
        :default-active="activeMenu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>

        <el-sub-menu index="inventory">
          <template #title>
            <el-icon><Box /></el-icon>
            <span>库存管理</span>
          </template>
          <el-menu-item index="/inventory">库存列表</el-menu-item>
          <el-menu-item index="/inventory/movements">库存流水</el-menu-item>
          <el-menu-item index="/inventory/operation">库存操作</el-menu-item>
          <el-menu-item index="/products">商品管理</el-menu-item>
          <el-menu-item index="/categories">分类管理</el-menu-item>
          <el-menu-item index="/units">单位管理</el-menu-item>
          <el-menu-item index="/warehouses">仓库管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="purchase">
          <template #title>
            <el-icon><ShoppingCart /></el-icon>
            <span>采购管理</span>
          </template>
          <el-menu-item index="/purchase">采购订单</el-menu-item>
          <el-menu-item index="/purchase/create">新建采购</el-menu-item>
          <el-menu-item index="/purchase-returns">采购退货</el-menu-item>
          <el-menu-item index="/suppliers">供应商管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="sales">
          <template #title>
            <el-icon><Suitcase /></el-icon>
            <span>销售管理</span>
          </template>
          <el-menu-item index="/sales">销售订单</el-menu-item>
          <el-menu-item index="/sales/create">新建销售</el-menu-item>
          <el-menu-item index="/sales-returns">销售退货</el-menu-item>
          <el-menu-item index="/customers">客户管理</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="reports">
          <template #title>
            <el-icon><TrendCharts /></el-icon>
            <span>报表统计</span>
          </template>
          <el-menu-item index="/reports/inventory-movements">流水汇总</el-menu-item>
          <el-menu-item index="/reports/low-stock">低库存预警</el-menu-item>
          <el-menu-item index="/reports/purchase">采购统计</el-menu-item>
          <el-menu-item index="/reports/sales">销售统计</el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="authStore.hasRole(['admin'])" index="settings">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item index="/settings/roles">角色管理</el-menu-item>
          <el-menu-item index="/settings/user-role">用户角色</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/help/usage">
          <el-icon><Reading /></el-icon>
          <span>使用说明</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-title">{{ currentTitle }}</div>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            {{ authStore.user?.username || '用户' }}
            <el-tag size="small" type="info" class="role-tag">
              {{ authStore.user?.role || 'operator' }}
            </el-tag>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  DataAnalysis,
  Box,
  ShoppingCart,
  Suitcase,
  TrendCharts,
  Setting,
  User,
  ArrowDown,
  Reading,
} from '@element-plus/icons-vue'

const route = useRoute()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string) || '进销存管理')

function handleCommand(command: string) {
  if (command === 'logout') {
    authStore.logout()
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}
.layout-aside {
  background-color: #304156;
  overflow-x: hidden;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  background-color: #2b3648;
}
.layout-aside .el-menu {
  border-right: none;
}
.layout-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.header-title {
  font-size: 16px;
  font-weight: 600;
}
.user-info {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}
.role-tag {
  margin-left: 4px;
}
.layout-main {
  background-color: #f0f2f5;
  padding: 16px;
}
</style>
