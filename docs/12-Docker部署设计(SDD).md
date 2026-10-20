# Docker 容器化部署设计 (SDD)

> 版本：v1.0
> 适用阶段：进销存系统全栈容器化部署（mysql / backend / frontend / redis）
> 目标：一条 `docker compose up -d --build` 命令拉起全部服务，数据持久化，支持扩容与迁移。

## 1. 服务划分

| 服务 | 镜像/构建 | 端口 | 作用 |
|------|----------|------|------|
| mysql | `mysql:8.0` | 3306 | 业务数据库，数据卷持久化 |
| redis | `redis:7-alpine` | - | 预留（token 黑名单/缓存），AOF 持久化 |
| backend | 构建 `Dockerfile.backend`（python:3.11-slim） | 8002 | FastAPI + uvicorn，启动时自动执行 alembic 迁移 + seed 角色 |
| frontend | 构建 `Dockerfile.frontend`（node:20 构建 → nginx:alpine） | 80(宿主3000) | 托管已 build 的 dist，nginx 反代 `/api` 到 backend |

## 2. 文件清单

| 文件 | 说明 |
|------|------|
| `Dockerfile.backend` | 后端镜像构建 |
| `Dockerfile.frontend` | 前端镜像多阶段构建 |
| `nginx.conf` | nginx 站点配置（SPA 回退 + /api 反代） |
| `docker-compose.yml` | 4 服务编排 |
| `.env.example` | 环境变量示例 |
| `.dockerignore` | 构建上下文排除规则 |
| `scripts/entrypoint.sh` | 后端启动入口（等 DB → 迁移 → seed → uvicorn） |
| `core/config.py`（修改） | 支持 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME` 环境变量 |

## 3. 网络与数据

- **网络**：自定义 bridge 网络 `inventory-net`，服务间通过服务名互访（如 `backend:8002`、`mysql:3306`）。
- **数据卷**：
  - `mysql_data` → 容器 `/var/lib/mysql`
  - `redis_data` → 容器 `/data`
- **环境变量注入**（compose `environment`）：
  - `DB_HOST=mysql`、`DB_PORT=3306`、`DB_USER=root`、`DB_PASSWORD`、`DB_NAME`
  - `SECRET_KEY`、`DEBUG=false`
  - MySQL 容器：`MYSQL_ROOT_PASSWORD`、`MYSQL_DATABASE`
- 宿主机通过 `.env` 文件向 compose 注入敏感值（`.env.example` 提供模板）。

## 4. 构建流程

### 4.1 后端
- 基础镜像 `python:3.11-slim`。
- 拷贝 `requirements.txt` → `pip install` → 拷贝源码。
- `CMD scripts/entrypoint.sh`：
  1. 轮询等待 MySQL 就绪（最多 60s）。
  2. `alembic upgrade head` 执行数据库迁移。
  3. `python scripts/seed_roles.py` 幂等初始化角色与权限。
  4. `exec uvicorn main:app --host 0.0.0.0 --port 8002`。

### 4.2 前端
- 阶段一 `node:20-alpine`：`npm install` → `npm run build`（产出 `dist/`）。
- 阶段二 `nginx:alpine`：拷贝 `dist` 到 `/usr/share/nginx/html`，覆盖 nginx 配置。

### 4.3 nginx 配置要点
- `location /` → SPA 回退到 `index.html`。
- `location /api/` → `proxy_pass http://backend:8002`，透传 `Host` / `X-Real-IP` 等头。

## 5. 启动顺序与健康检查

`depends_on` + `condition`：
- `backend` 依赖 `mysql`（`service_healthy`）、`redis`（`service_started`）。
- `frontend` 依赖 `backend`（`service_started`）。

健康检查：
- **mysql**：`mysqladmin ping`。
- **redis**：`redis-cli ping`。
- **backend**：`python` 访问 `http://localhost:8002/health`。
- **frontend**：`wget -q --spider http://localhost/`。

全部服务 `restart: unless-stopped`。

## 6. 初始化与幂等

- 首次启动：MySQL 自动创建 `MYSQL_DATABASE` 库；backend 执行 alembic 建表 + seed_roles 插入 admin/operator 角色与权限。
- `seed_roles.py` 本身幂等（已存在则跳过），可重复执行。
- 不自动创建 admin 用户——admin 用户需在部署后通过注册接口或手动 SQL 创建（避免弱口令泄露）。

## 7. 约束与风险

1. **生产环境**务必修改 `.env` 中的 `DB_PASSWORD` 与 `SECRET_KEY`，切勿使用示例值。
2. MySQL 8.0 默认 `caching_sha2_password`，PyMySQL 支持，无需额外配置。
3. 前端镜像构建依赖 npm 网络，内网环境需配置 npm 镜像源。
4. 后端镜像未做非 root 用户运行，生产可进一步加固。
