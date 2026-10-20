"""Excel 导出工具。

基于 openpyxl 生成 .xlsx 字节流，并通过 FastAPI Response 流式返回。
- build_excel_bytes：根据表头与数据行构建单 Sheet 工作簿字节。
- build_multi_sheet_excel_bytes：构建多 Sheet 工作簿字节（用于统计类导出）。
- excel_response：包装为带正确 Content-Type / Content-Disposition 的响应。
"""

from __future__ import annotations

import io
from datetime import datetime
from urllib.parse import quote

from fastapi import Response
from openpyxl import Workbook


def build_excel_bytes(headers: list[str], rows: list[list]) -> bytes:
    """构建单 Sheet xlsx 字节流。

    Args:
        headers: 表头列表。
        rows: 数据行列表，每行元素与 headers 一一对应。
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "数据"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_multi_sheet_excel_bytes(
    sheets: list[tuple[str, list[str], list[list]]],
) -> bytes:
    """构建多 Sheet xlsx 字节流。

    Args:
        sheets: [(sheet_name, headers, rows), ...]
    """
    wb = Workbook()
    # 移除默认 Sheet，后续按需追加
    wb.remove(wb.active)
    for name, headers, rows in sheets:
        ws = wb.create_sheet(title=name)
        ws.append(headers)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def excel_response(data: bytes, filename: str) -> Response:
    """返回带正确 Content-Type / Content-Disposition 的流式响应。

    Args:
        data: xlsx 字节流。
        filename: 下载文件名（建议带日期戳）。
    """
    # RFC 5987 编码中文文件名
    encoded = quote(filename)
    return Response(
        content=data,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


def dated_filename(base: str) -> str:
    """生成带日期戳的文件名：{base}_{YYYYMMDDHHMMSS}.xlsx"""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base}_{ts}.xlsx"
