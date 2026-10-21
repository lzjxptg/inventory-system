<template>
  <div class="usage-guide">
    <div class="guide-header">
      <h2>📖 进销存管理系统使用说明</h2>
      <el-button type="primary" link @click="scrollToTop">回到顶部</el-button>
    </div>
    <div class="markdown-body" v-html="html" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import usageMd from '../../../docs/15-使用说明.md?raw'

// 配置 marked：开启 GitHub 风格换行、代码高亮类名
marked.setOptions({
  gfm: true,
  breaks: true,
})

const html = computed(() => marked.parse(usageMd) as string)

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>

<style scoped>
.usage-guide {
  padding: 20px;
  max-width: 1100px;
  margin: 0 auto;
}

.guide-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 12px;
  margin-bottom: 20px;
}

.guide-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

/* markdown 样式 */
.markdown-body {
  color: #303133;
  font-size: 14px;
  line-height: 1.7;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  color: #1f2937;
  font-weight: 600;
  margin-top: 24px;
  margin-bottom: 12px;
}

.markdown-body :deep(h1) { font-size: 22px; border-bottom: 1px solid #ebeef5; padding-bottom: 8px; }
.markdown-body :deep(h2) { font-size: 18px; border-bottom: 1px solid #ebeef5; padding-bottom: 6px; }
.markdown-body :deep(h3) { font-size: 16px; }

.markdown-body :deep(p) { margin: 8px 0; }

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #dcdfe6;
  padding: 8px 12px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}

.markdown-body :deep(tr:nth-child(even)) {
  background: #fafafa;
}

.markdown-body :deep(code) {
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #c7254e;
}

.markdown-body :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 14px 16px;
  border-radius: 6px;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.markdown-body :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 16px;
  border-left: 4px solid #409eff;
  background: #ecf5ff;
  color: #606266;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 24px;
  margin: 8px 0;
}

.markdown-body :deep(li) { margin: 4px 0; }

.markdown-body :deep(a) {
  color: #409eff;
  text-decoration: none;
}

.markdown-body :deep(a:hover) { text-decoration: underline; }

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #ebeef5;
  margin: 20px 0;
}
</style>
