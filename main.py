"""进销存管理系统 FastAPI 应用入口。

负责创建应用实例、配置 CORS、注册全局异常处理器与全部 API 路由，
并提供健康检查端点。数据库表结构由 Alembic 或手动管理，本文件不建表。
"""

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.staticfiles import StaticFiles

from core.dependencies import get_current_user
from core.exceptions import register_exception_handlers
from routers import (
    auth,
    category,
    customer,
    inventory,
    product,
    purchase,
    reports,
    roles,
    sales,
    supplier,
    unit,
    users,
    warehouse,
)

app = FastAPI(
    title="进销存管理系统 API",
    description="基于 FastAPI + SQLAlchemy 2.x 的进销存系统",
    version="1.0.0",
    docs_url=None,
    redoc_url="/redoc",
)

# 挂载本地 Swagger 静态资源目录，解决 CDN 不可达导致的白屏问题
current_file_dir = Path(__file__).parent
swagger_static_dir = current_file_dir / "static" / "swagger"
app.mount(
    "/static/swagger",
    StaticFiles(directory=swagger_static_dir),
    name="swagger_static",
)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自定义 Swagger UI 页面，引用本地静态资源。"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="/static/swagger/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger/swagger-ui.css",
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
app.include_router(category.router, dependencies=PROTECTED)
app.include_router(unit.router, dependencies=PROTECTED)
app.include_router(product.router, dependencies=PROTECTED)
app.include_router(supplier.router, dependencies=PROTECTED)
app.include_router(customer.router, dependencies=PROTECTED)
app.include_router(warehouse.router, dependencies=PROTECTED)
app.include_router(inventory.router, dependencies=PROTECTED)
app.include_router(purchase.router, prefix="/api/v1/purchases", dependencies=PROTECTED)
app.include_router(sales.router, prefix="/api/v1/sales", dependencies=PROTECTED)
app.include_router(reports.router, dependencies=PROTECTED)
app.include_router(roles.router, dependencies=PROTECTED)
app.include_router(users.router, dependencies=PROTECTED)


@app.get("/health")
def health_check():
    """健康检查端点。"""
    return {"status": "ok", "msg": "进销存系统 API 运行中"}


@app.on_event("startup")
def on_startup() -> None:
    """启动时打印已注册的路由清单，便于核对。"""
    print(f"[startup] {app.title} v{app.version} 启动完成")
    print(f"[startup] 已注册路由数：{len(app.routes)}")
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if methods and path:
            print(f"  {methods} {path}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
