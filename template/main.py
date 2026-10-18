"""FastAPI 应用入口（模板精简版）。

仅挂载鉴权路由，作为最小可运行骨架。
新增业务模块请参考底部 checklist。
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.dependencies import get_current_user
from core.exceptions import register_exception_handlers
from routers import auth

app = FastAPI(
    title="{{project_name}} API",
    description="基于 FastAPI + SQLAlchemy 2.x 的项目模板",
    version="0.1.0",
)

# CORS 中间件：开发阶段允许所有来源，生产环境应指定具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器（BusinessException 及未捕获异常）
register_exception_handlers(app)

# 鉴权路由（注册/登录）不做鉴权保护
app.include_router(auth.router)

# 业务路由统一加上登录鉴权依赖（不修改各 router 内部实现）
PROTECTED = [Depends(get_current_user)]
# 示例：app.include_router(xxx.router, dependencies=PROTECTED)


@app.get("/health")
def health_check():
    """健康检查端点。"""
    return {"status": "ok", "msg": "{{project_name}} API 运行中"}


# ===========================================================================
# 新增业务模块 checklist
# ===========================================================================
# 1. models/xxx.py 定义模型（继承 Base + CommonMixin）→ models/__init__.py 注册
# 2. schemas/xxx.py 定义请求/响应 Schema（继承 _BaseSchema）
# 3. crud/xxx.py 写数据库操作，业务异常统一抛 BusinessException 子类
#    （NotFoundException 40401 / ValidationException 40001 / ConflictException 40901）
# 4. routers/xxx.py 写端点，响应用 success(data=...) 包装，加 PROTECTED 鉴权
# 5. main.py 挂载路由：app.include_router(xxx.router, dependencies=PROTECTED)
# 6. alembic revision --autogenerate -m "add xxx tables" → 人工核对 → upgrade head
# 7. tests/test_xxx.py 写测试，复用 conftest.py 的 db_session / auth_client
# ===========================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
