# {{project_name}} 项目模板

基于 **FastAPI + SQLAlchemy 2.x + MySQL + Alembic + pytest** 的后端项目脚手架。
内置：统一响应、BusinessException 异常体系、JWT 鉴权、事务回滚测试基础设施、分层架构示例。

---

## 快速启动

### 一键初始化（推荐）

```bash
# 进入模板目录
cd template

# 交互式初始化（按需输入项目名、数据库等信息）
python init_template.py

# 或非交互式，一次传完所有参数
python init_template.py --name my-project --db my_project --db-user root --db-pass yourpass
```

脚本会自动：
- 在当前目录下创建 `my-project/` 新项目目录
- 替换所有 `{{project_name}}`、`{{db_name}}` 等占位符
- 生成随机 `SECRET_KEY`
- 生成已填入真实值的 `.env` 文件

---

### 手动步骤（5 步）

1. **创建虚拟环境并安装依赖**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   pip install -e ".[test]"
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env，填入 DATABASE_URL、SECRET_KEY 等
   ```

3. **创建数据库表**
   ```bash
   # 开发环境快速建表
   python scripts/init_db.py
   # 或使用 Alembic 迁移
   alembic upgrade head
   ```

4. **启动服务**
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   访问 http://localhost:8000/docs 查看 Swagger UI。

5. **运行测试**
   ```bash
   pytest tests/ -v
   ```

---

## 项目结构

```
{{project_name}}/
├── alembic/                  # 数据库迁移
│   ├── env.py
│   ├── script.py.mako
│   └── versions/             # 迁移脚本
├── alembic.ini
├── core/                     # 基础设施层
│   ├── config.py             # 配置（pydantic-settings，从 .env 读取）
│   ├── database.py           # engine / SessionLocal / Base / get_db
│   ├── dependencies.py       # get_current_user（JWT 鉴权依赖）
│   ├── exceptions.py         # BusinessException 体系 + 全局处理器
│   ├── response.py           # success() / error() 统一响应
│   └── security.py           # bcrypt 密码哈希 + JWT 签发/校验
├── models/                   # ORM 模型（继承 Base + CommonMixin）
│   ├── base.py               # CommonMixin（id / is_deleted / created_at）
│   └── user.py               # 用户表示例
├── schemas/                  # Pydantic 请求/响应 Schema
│   ├── __init__.py           # _BaseSchema 基类（from_attributes=True）
│   └── user.py               # 用户 Schema 示例
├── crud/                     # 数据库操作层（业务异常抛 BusinessException）
│   └── user.py               # 用户 CRUD 示例
├── routers/                  # API 路由层
│   └── auth.py               # 注册/登录示例
├── tests/
│   ├── conftest.py           # 测试基础设施（事务回滚 / auth_client）
│   └── test_health.py        # 示例测试
├── scripts/
│   └── init_db.py            # 建表脚本
├── main.py                   # 应用入口
├── pyproject.toml
└── .env.example
```

---

## 分层架构

```
routers（HTTP 层）  →  crud（数据库层）  →  models（ORM）
      ↓                     ↓
  schemas（校验）     BusinessException
      ↓                     ↓
  success/error        全局异常处理器
```

| 层 | 职责 | 异常处理 |
|----|------|----------|
| routers | 接收请求、参数校验、调用 crud、包装响应 | 不直接抛 HTTPException |
| crud | 数据库读写、业务校验、事务控制 | 抛 BusinessException 子类 |
| models | 表结构定义 | — |
| schemas | 请求/响应数据结构 + 校验 | Pydantic 自动 422 |

---

## 异常体系

所有业务异常继承 `BusinessException`，由全局处理器统一返回 **HTTP 200 + `{code, msg, data}`**。

| 异常类 | code | 场景 |
|--------|------|------|
| `ValidationException` | 40001 | 参数校验失败 |
| `UnauthorizedException` | 40101 | 未授权 / Token 无效 |
| `NotFoundException` | 40401 | 资源不存在 |
| `ConflictException` | 40901 | 业务冲突（重复、状态非法等） |
| 未捕获异常 | 50000 | 系统异常（不暴露堆栈） |

> Pydantic 校验失败仍返回 HTTP 422（框架层，不受影响）。

### 统一响应格式

```json
{"code": 0, "msg": "ok", "data": ...}
```

成功用 `success(data=...)`，失败在 crud 层抛异常即可，路由层无需手动 `error()`。

---

## 测试运行

```bash
# 全量测试
pytest tests/ -v

# 单个文件
pytest tests/test_health.py -v

# 带覆盖率
pytest tests/ --cov=routers --cov=crud
```

**测试基础设施**（`tests/conftest.py`）：
- 自动创建独立测试库 `{{db_name}}_test`
- 每个用例在独立事务中运行，结束后回滚（`join_transaction_mode="create_savepoint"`）
- `db_session` fixture：直接查库，绕过缓存
- `auth_client` fixture：自动创建测试用户并登录，返回带 JWT 的 httpx 客户端

---

## 新增业务模块 Checklist

1. **models/xxx.py**：定义模型（继承 `Base + CommonMixin`）
2. **models/__init__.py**：注册新模型，确保 Alembic 能识别
3. **schemas/xxx.py**：定义 Create / Update / Response Schema（继承 `_BaseSchema`）
4. **crud/xxx.py**：写数据库操作，业务异常抛 `BusinessException` 子类
5. **routers/xxx.py**：写端点，响应 `success(data=...)`，加 `PROTECTED` 鉴权
6. **main.py**：`app.include_router(xxx.router, dependencies=PROTECTED)`
7. **alembic revision --autogenerate -m "add xxx tables"** → 人工核对 → `alembic upgrade head`
8. **tests/test_xxx.py**：复用 `db_session` / `auth_client` 写测试

---

## 数据库迁移

```bash
# 生成迁移脚本（自动检测模型变化）
alembic revision --autogenerate -m "add xxx tables"

# 人工核对 alembic/versions/<rev>_xxx.py 后执行升级
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 查看当前版本
alembic current
```
