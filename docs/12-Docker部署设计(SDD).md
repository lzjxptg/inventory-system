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

## 8. 实际踩坑与解决方案

以下均为本项目在 Windows + Docker Desktop 环境下真实遇到并解决的问题。

### 8.1 中文目录名导致 compose 项目名异常

**现象**：项目目录为 `进销存练习`（中文），直接 `docker compose up` 时 compose 自动推导的项目名包含非 ASCII 字符，在部分 Docker Desktop 版本下会导致容器名/网络名解析异常或日志乱码。

**解决方案**：显式指定 `-p inventory` 指定 compose 项目名，容器名统一为 `inventory-*`。所有 compose 命令均带该参数：

```bash
docker compose -p inventory up -d --build
docker compose -p inventory ps
docker compose -p inventory logs -f backend
```

### 8.2 宿主机 3306 端口被占用

**现象**：开发机本地已运行 MySQL，占用 3306，导致 `mysql` 服务端口映射冲突、启动失败。

**解决方案**：在 `.env` 中设置 `MYSQL_HOST_PORT=3307`，compose 中使用 `"${MYSQL_HOST_PORT:-3306}:3306"`。服务间仍通过 `mysql:3306` 互访，仅宿主机访问用 3307。

### 8.3 IPv6 下 nginx healthcheck 失败

**现象**：frontend 容器 healthcheck 用 `wget --spider http://localhost/`，在某些 Docker 网络配置下 `localhost` 解析到 `::1`，而 nginx 仅监听 IPv4，导致 healthcheck 持续失败。

**解决方案**：`nginx.conf` 同时监听 IPv4 和 IPv6：

```nginx
listen 80;
listen [::]:80;
```

确保 `localhost` 无论解析到 `127.0.0.1` 还是 `::1` 均可连通。

### 8.4 BuildKit 构建时代理不走 daemon 配置

**现象**：Docker Desktop 配置了系统代理，但 `docker build`（BuildKit）拉取基础镜像或 pip/npm 安装时不走该代理，导致构建超时。BuildKit 的构建容器与 daemon 是隔离的，daemon 级代理不自动透传到构建步骤。

**解决方案（workaround）**：
- 方式一：在 `Dockerfile` 中通过 `ARG` 显式传入代理，并在需要网络的 `RUN` 步骤前设置 `http_proxy` / `https_proxy` 环境变量，构建完成后取消设置。
- 方式二：使用 Docker Desktop 的 **Settings → Resources → Proxies → Manual proxy configuration**，填入 `http://host.docker.internal:3128`（需本机运行代理客户端并开启 3128 端口）。该方式对 BuildKit 同样生效。

> 本项目最终采用方式二，详见 §9。

### 8.5 Docker Hub 镜像拉取失败

**现象**：`mysql:8.0`、`python:3.11-slim`、`node:20-alpine` 等镜像从 Docker Hub 拉取超时或失败。

**解决方案**：配置 Docker Desktop 镜像加速器（国内可用阿里云 / 网易云等加速地址），或使用代理。配置路径：Docker Desktop → Settings → Docker Engine，在 JSON 中添加 `registry-mirrors`。

## 9. 最终生效的代理方案

构建与运行阶段的网络代理统一通过 **Docker Desktop Manual proxy** 配置：

1. 启动本机代理客户端（如 Clash / V2Ray），确保 HTTP 代理端口监听（示例 `3128`）。
2. Docker Desktop → **Settings → Resources → Proxies** → 选择 **Manual proxy configuration**。
3. Web Server (HTTP) 与 Secure Web Server (HTTPS) 均填入：

   ```
   http://host.docker.internal:3128
   ```

   （`host.docker.internal` 是容器访问宿主机的特殊 DNS 名，Docker Desktop 自动解析。）

4. **Apply & Restart** 让配置生效。

验证方式：

```bash
docker compose -p inventory build backend --no-cache
# 观察 pip install 是否能正常下载依赖包
```

> 注意：`host.docker.internal` 在 Linux Docker Engine 上需额外加 `--add-host=host.docker.internal:host-gateway`，Docker Desktop（Windows/macOS）默认支持。

## 10. 服务健康状态确认

### 10.1 compose 层面

```bash
docker compose -p inventory ps
```

预期 4 个服务 `STATUS` 均为 `Up ... (healthy)`：

| 服务 | STATUS |
|------|--------|
| inventory-mysql | Up (healthy) |
| inventory-redis | Up (healthy) |
| inventory-backend | Up (healthy) |
| inventory-frontend | Up (healthy) |

健康检查定义（见 `docker-compose.yml`）：

- **mysql**：`mysqladmin ping -h localhost -u root -p$DB_PASSWORD`，每 10s 一次，重试 10 次。
- **redis**：`redis-cli ping`，每 10s 一次，重试 5 次。
- **backend**：`python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"`，每 15s 一次，启动宽限期 30s。
- **frontend**：`wget -q --spider http://localhost/`，每 15s 一次。

### 10.2 后端健康端点

直接访问 `http://localhost:8002/health`，预期返回：

```json
{"status": "ok", "msg": "进销存系统 API 运行中"}
```

### 10.3 数据库内数据核验

```bash
# 确认角色与权限绑定（admin 应绑定 12 条权限）
docker compose -p inventory exec mysql mysql -uroot -p$DB_PASSWORD -D inventory -e \
  "SELECT r.name, COUNT(rp.permission_id) AS perm_count FROM roles r LEFT JOIN role_permissions rp ON r.id=rp.role_id GROUP BY r.id, r.name;"
```

预期输出：

```
name    perm_count
admin   12
operator  8
```

### 10.4 前端可访问性

浏览器访问 `http://localhost:3000`，应能打开登录页；用 admin 账号登录后可正常加载菜单与数据。
