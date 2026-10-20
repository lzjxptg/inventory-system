# 进销存管理系统

一套面向中小企业的进销存（进货 / 销售 / 库存）管理系统，支持角色权限管理、库存流水、采购销售全流程、Excel 报表导出与数据仪表盘。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 · FastAPI 0.143 · SQLAlchemy 2.x · Alembic · PyMySQL · Pydantic v2 |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7（预留 token 黑名单 / 缓存） |
| 前端 | Vue 3.5 · TypeScript 6 · Vite 8 · Element Plus 2 · Pinia · Vue Router · ECharts |
| 部署 | Docker Compose（mysql / redis / backend / frontend 四服务） |

## 功能清单

- **RBAC 权限管理**：admin / operator 双角色，12 项权限码（角色管理、用户分配角色、采购/销售/库存/报表的查看与增删），接口级权限校验，前端路由守卫 + 按钮级 `v-permission`。
- **基础档案**：商品、分类、单位、仓库、供应商、客户的增删改查（逻辑删除）。
- **库存管理**：入库、出库、盘点调整、库存余额查询、库存流水查询；出库自动校验库存充足。
- **采购管理**：采购订单（创建/提交/审核/取消/删除）+ 采购入库单（创建/确认/取消），确认入库联动库存。
- **销售管理**：销售订单（创建/提交/审核/取消/删除）+ 销售出库单（创建/确认/取消），确认出库联动库存。
- **报表统计**：库存流水汇总、低库存预警、采购金额统计、销售金额统计。
- **Excel 导出**：6 个模块一键导出 `.xlsx`（库存流水、采购订单、销售订单、低库存预警、采购统计、销售统计），统计类导出为双 Sheet。
- **仪表盘**：数据可视化看板。

## 快速启动（Docker 一键部署）

> 前提：已安装 Docker Desktop 并启动。

```bash
# 1. 进入项目目录
cd 进销存练习

# 2. 复制环境变量模板并按需修改（生产环境务必改 DB_PASSWORD 和 SECRET_KEY）
cp .env.example .env

# 3. 一键构建并启动全部服务
docker compose -p inventory up -d --build
```

启动后：

- 前端访问：http://localhost:3000
- 后端 API 文档：http://localhost:8002/docs（本地 Swagger 静态资源，无需外网）
- MySQL：`localhost:3307`，库名 `inventory`

### 初始化 admin 账号

容器启动时 entrypoint 会自动执行 `alembic upgrade head`（建表）和 `seed_roles.py`（初始化角色与权限）。admin 用户需手动创建：

```bash
# 注册 admin 用户
curl -X POST http://localhost:8002/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123456","phone":"13800000000"}'

# 将 admin 用户提升为管理员角色（重新执行 seed_roles，它会把名为 admin 的用户绑定到 admin 角色）
docker compose -p inventory exec backend python scripts/seed_roles.py
```

之后即可用 `admin / admin123456` 登录系统。

### 常用命令

```bash
# 查看服务状态
docker compose -p inventory ps

# 查看后端日志
docker compose -p inventory logs -f backend

# 停止并销毁容器（数据卷保留）
docker compose -p inventory down

# 停止并销毁容器及数据卷（清空数据库）
docker compose -p inventory down -v
```

## 默认端口

| 服务 | 容器内端口 | 宿主机端口 |
|------|-----------|-----------|
| frontend（nginx） | 80 | 3000 |
| backend（uvicorn） | 8002 | 8002 |
| mysql | 3306 | 3307 |
| redis | 6379 | 不映射 |

## 环境变量说明

项目通过 `.env` 文件（由 `.env.example` 复制而来）向 Docker Compose 注入配置。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DB_PASSWORD` | `123456` | MySQL root 用户密码，同时供后端连接数据库使用。**生产环境必须修改**。 |
| `DB_NAME` | `inventory` | 业务数据库名，MySQL 容器首次启动时自动创建该库。 |
| `SECRET_KEY` | `your-super-secret-key-change-me` | JWT 签名密钥。**生产环境必须修改为长随机串**，否则 token 可被伪造。 |
| `MYSQL_HOST_PORT` | `3306` | MySQL 映射到宿主机的端口。若宿主机 3306 被占用，可改为 `3307` 等。 |

> 说明：`DB_HOST`、`DB_PORT`、`DB_USER`、`DEBUG` 等变量在 `docker-compose.yml` 中通过 `environment` 直接注入（`DB_HOST=mysql`、`DB_PORT=3306`、`DB_USER=root`、`DEBUG=false`），无需在 `.env` 中配置。

## 项目结构

```
进销存练习/
├── alembic/              # 数据库迁移
├── core/                 # 基础设施（配置、数据库、鉴权、响应、权限、Excel 导出）
├── crud/                 # 数据访问层（SQLAlchemy 2.x select 风格）
├── docs/                 # 设计文档（SDD）
├── frontend/             # Vue3 + TS 前端
├── models/               # SQLAlchemy ORM 模型
├── routers/              # FastAPI 路由
├── schemas/              # Pydantic 请求/响应模型
├── scripts/              # 启动入口与 seed 脚本
├── tests/                # pytest 测试
├── docker-compose.yml    # 四服务编排
├── Dockerfile.backend    # 后端镜像
├── Dockerfile.frontend   # 前端镜像（多阶段构建）
├── nginx.conf            # nginx 配置（SPA 回退 + /api 反代）
├── main.py               # FastAPI 应用入口
└── requirements.txt      # Python 依赖
```

## 默认账号

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| admin | admin123456 | admin | 超级管理员，拥有全部 12 项权限 |

> admin 账号需按上方「初始化 admin 账号」步骤手动创建并绑定角色。
