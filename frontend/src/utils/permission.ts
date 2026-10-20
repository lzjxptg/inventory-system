import type { Directive } from 'vue'
import { useAuthStore } from '@/stores/auth'

/**
 * v-permission 自定义指令：按权限 code 控制按钮/元素显隐。
 * 用法：
 *   <el-button v-permission="'purchase:delete'">删除</el-button>
 *   <el-button v-permission="['purchase:delete', 'sales:delete']">删除</el-button>
 */
export const permissionDirective: Directive = {
  mounted(el, binding) {
    const auth = useAuthStore()
    const needed = binding.value
    if (!needed) return
    const ok = Array.isArray(needed)
      ? needed.some((p) => auth.permissions.includes(p))
      : auth.permissions.includes(needed)
    if (!ok) {
      el.parentNode?.removeChild(el)
    }
  },
}
