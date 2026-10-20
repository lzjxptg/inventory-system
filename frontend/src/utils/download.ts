// 通用文件下载工具

/**
 * 触发浏览器下载 Blob。
 * @param blob 文件二进制
 * @param filename 下载文件名（可选，缺省 export.xlsx）
 */
export function downloadBlob(blob: Blob, filename?: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'export.xlsx'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
