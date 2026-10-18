from typing import Any


def success(data: Any = None, msg: str = "ok") -> dict:
    """成功响应。

    返回格式：{"code": 0, "msg": "ok", "data": ...}
    """
    return {"code": 0, "msg": msg, "data": data}


def error(code: int, msg: str, data: Any = None) -> dict:
    """失败响应。

    返回格式：{"code": code, "msg": msg, "data": data}
    """
    return {"code": code, "msg": msg, "data": data}
