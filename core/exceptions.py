import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class BusinessException(Exception):
    """业务异常基类。

    所有业务层抛出的异常都应继承此类，由全局异常处理器统一捕获并返回 JSON。
    """

    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg
        super().__init__(msg)


class NotFoundException(BusinessException):
    """资源不存在，code=40401。"""

    def __init__(self, msg: str = "资源不存在"):
        super().__init__(code=40401, msg=msg)


class ValidationException(BusinessException):
    """参数校验失败，code=40001。"""

    def __init__(self, msg: str = "参数校验失败"):
        super().__init__(code=40001, msg=msg)


class ConflictException(BusinessException):
    """业务冲突（库存不足、存在子分类等），code=40901。"""

    def __init__(self, msg: str = "业务冲突"):
        super().__init__(code=40901, msg=msg)


class UnauthorizedException(BusinessException):
    """未授权，code=40101。"""

    def __init__(self, msg: str = "未授权"):
        super().__init__(code=40101, msg=msg)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。

    - BusinessException → 返回业务 code/msg，HTTP 状态码 200
    - 其他未捕获异常 → 返回 50000 系统异常，HTTP 状态码 200，不暴露堆栈
    """

    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        return JSONResponse(
            status_code=200,
            content={"code": exc.code, "msg": exc.msg, "data": None},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # 后端记录完整异常堆栈，前端只返回通用提示
        logger.exception("未捕获的系统异常: %s", exc)
        return JSONResponse(
            status_code=200,
            content={"code": 50000, "msg": "系统异常", "data": None},
        )
