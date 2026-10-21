"""用户管理端点测试。

覆盖：
- POST /api/v1/users（正常创建、重复用户名、指定角色、无权限）
- DELETE /api/v1/users/{id}（正常删除、删除自己、删除不存在、删 admin 后剩最后一个、无权限）
- PUT /api/v1/users/{id}/reset-password（正常重置、不存在、无权限）
所有测试在独立事务中运行，结束后自动回滚。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import get_password_hash, verify_password
from crud.user import count_active_admins
from models.role import Role
from models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_client(client: AsyncClient, db_session: Session):
    """带 admin 角色 JWT 的测试客户端。"""
    role = Role(name="admin", description="管理员")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    user = User(
        username="admintest",
        hashed_password=get_password_hash("adminpass123"),
        is_active=True,
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "admintest", "password": "adminpass123"},
    )
    token = r.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    yield client


# ---------------------------------------------------------------------------
# POST /api/v1/users — 创建用户
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_success(admin_client: AsyncClient, db_session: Session):
    """admin 可创建用户，返回不含密码的用户信息，密码已哈希。"""
    resp = await admin_client.post(
        "/api/v1/users",
        json={"username": "newuser", "password": "pass12345"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["username"] == "newuser"
    assert "hashed_password" not in body["data"]
    assert "password" not in body["data"]

    u = db_session.execute(
        select(User).where(User.username == "newuser")
    ).scalar_one()
    assert verify_password("pass12345", u.hashed_password)


@pytest.mark.asyncio
async def test_create_user_with_role(admin_client: AsyncClient, db_session: Session):
    """创建用户时可指定 role_id。"""
    role = Role(name="custom_role", description="自定义")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    resp = await admin_client.post(
        "/api/v1/users",
        json={"username": "roleduser", "password": "pass12345", "role_id": role.id},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role_id"] == role.id


@pytest.mark.asyncio
async def test_create_user_invalid_role(admin_client: AsyncClient):
    """指定不存在的 role_id 返回 40001。"""
    resp = await admin_client.post(
        "/api/v1/users",
        json={"username": "badrole", "password": "pass12345", "role_id": 999999},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001


@pytest.mark.asyncio
async def test_create_user_duplicate_username(admin_client: AsyncClient):
    """重复用户名返回 40901 冲突。"""
    await admin_client.post(
        "/api/v1/users",
        json={"username": "dupuser", "password": "pass12345"},
    )
    resp = await admin_client.post(
        "/api/v1/users",
        json={"username": "dupuser", "password": "pass12345"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901


@pytest.mark.asyncio
async def test_create_user_operator_forbidden(auth_client: AsyncClient):
    """operator（默认角色）创建用户应返回 40301。"""
    resp = await auth_client.post(
        "/api/v1/users",
        json={"username": "opuser", "password": "pass12345"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40301


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/{id} — 删除用户
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_user_success(admin_client: AsyncClient, db_session: Session):
    """admin 可逻辑删除其他用户。"""
    user = User(
        username="deluser",
        hashed_password=get_password_hash("pass12345"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = await admin_client.delete(f"/api/v1/users/{user.id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    u = db_session.execute(
        select(User).where(User.id == user.id)
    ).scalar_one()
    assert u.is_deleted == 1


@pytest.mark.asyncio
async def test_delete_user_self_forbidden(admin_client: AsyncClient, db_session: Session):
    """不能删除当前登录用户自己。"""
    me = db_session.execute(
        select(User).where(User.username == "admintest")
    ).scalar_one()

    resp = await admin_client.delete(f"/api/v1/users/{me.id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001


@pytest.mark.asyncio
async def test_delete_user_not_found(admin_client: AsyncClient):
    """删除不存在的用户返回 40401。"""
    resp = await admin_client.delete("/api/v1/users/999999")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40401


@pytest.mark.asyncio
async def test_delete_admin_leaves_last_one_protected(
    admin_client: AsyncClient, db_session: Session
):
    """删除另一个 admin 后仅剩当前 admin；此时当前 admin 无法被删除（自删保护），
    从而保证至少保留一个管理员。同时校验 count_active_admins 计数。"""
    admin_role = db_session.execute(
        select(Role).where(Role.name == "admin")
    ).scalar_one()

    # 初始只有 admintest 一个 active admin
    assert count_active_admins(db_session, admin_role.id) == 1

    # 创建第二个 active admin
    other = User(
        username="admin2",
        hashed_password=get_password_hash("pass12345"),
        is_active=True,
        role_id=admin_role.id,
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    assert count_active_admins(db_session, admin_role.id) == 2

    # 删除第二个 admin 应成功（此时还有 admintest）
    resp = await admin_client.delete(f"/api/v1/users/{other.id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert count_active_admins(db_session, admin_role.id) == 1

    # 仅剩 admintest 一个 active admin，删除自己被自删保护拦截
    me = db_session.execute(
        select(User).where(User.username == "admintest")
    ).scalar_one()
    resp = await admin_client.delete(f"/api/v1/users/{me.id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40001


@pytest.mark.asyncio
async def test_delete_user_operator_forbidden(auth_client: AsyncClient, db_session: Session):
    """operator 删除用户应返回 40301。"""
    user = User(
        username="target_op",
        hashed_password=get_password_hash("pass12345"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = await auth_client.delete(f"/api/v1/users/{user.id}")
    assert resp.status_code == 200
    assert resp.json()["code"] == 40301


# ---------------------------------------------------------------------------
# PUT /api/v1/users/{id}/reset-password — 重置密码
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_success(admin_client: AsyncClient, db_session: Session):
    """admin 可重置任意用户密码，旧密码失效、新密码生效。"""
    user = User(
        username="reset_user",
        hashed_password=get_password_hash("oldpass123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = await admin_client.put(
        f"/api/v1/users/{user.id}/reset-password",
        json={"new_password": "newpass456"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    u = db_session.execute(
        select(User).where(User.id == user.id)
    ).scalar_one()
    assert verify_password("newpass456", u.hashed_password)
    assert not verify_password("oldpass123", u.hashed_password)


@pytest.mark.asyncio
async def test_reset_password_not_found(admin_client: AsyncClient):
    """重置不存在用户的密码返回 40401。"""
    resp = await admin_client.put(
        "/api/v1/users/999999/reset-password",
        json={"new_password": "newpass456"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40401


@pytest.mark.asyncio
async def test_reset_password_operator_forbidden(auth_client: AsyncClient, db_session: Session):
    """operator 重置密码应返回 40301。"""
    user = User(
        username="reset_target_op",
        hashed_password=get_password_hash("oldpass123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = await auth_client.put(
        f"/api/v1/users/{user.id}/reset-password",
        json={"new_password": "newpass456"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40301


# ---------------------------------------------------------------------------
# GET /api/v1/users — 用户列表
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_users_list(admin_client: AsyncClient):
    """获取用户列表，返回数组且包含 admin 用户。"""
    resp = await admin_client.get("/api/v1/users")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    usernames = [u["username"] for u in body["data"]]
    assert "admintest" in usernames


@pytest.mark.asyncio
async def test_get_users_pagination(admin_client: AsyncClient, db_session: Session):
    """列表分页参数 skip/limit 生效。"""
    # 准备 3 个额外用户
    for i in range(3):
        db_session.add(User(
            username=f"pageuser{i}",
            hashed_password=get_password_hash("pass12345"),
            is_active=True,
        ))
    db_session.commit()

    # limit=1 只返回 1 条
    resp = await admin_client.get("/api/v1/users", params={"skip": 0, "limit": 1})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    # skip=1 跳过第一条
    resp0 = await admin_client.get("/api/v1/users", params={"skip": 0, "limit": 1})
    resp1 = await admin_client.get("/api/v1/users", params={"skip": 1, "limit": 1})
    assert resp0.json()["data"][0]["id"] != resp1.json()["data"][0]["id"]


# ---------------------------------------------------------------------------
# PUT /api/v1/users/{id}/role — 角色分配
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user_role(admin_client: AsyncClient, db_session: Session):
    """admin 可修改用户角色。"""
    role_a = Role(name="role_a", description="A")
    role_b = Role(name="role_b", description="B")
    db_session.add_all([role_a, role_b])
    db_session.commit()
    db_session.refresh(role_a)
    db_session.refresh(role_b)

    user = User(
        username="rolechg",
        hashed_password=get_password_hash("pass12345"),
        is_active=True,
        role_id=role_a.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = await admin_client.put(
        f"/api/v1/users/{user.id}/role",
        json={"role_id": role_b.id},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["role_id"] == role_b.id

    u = db_session.execute(
        select(User).where(User.id == user.id)
    ).scalar_one()
    assert u.role_id == role_b.id


@pytest.mark.asyncio
async def test_update_user_role_nonexistent(admin_client: AsyncClient, db_session: Session):
    """修改不存在用户的角色返回 code 404。"""
    role = Role(name="r_nonexist", description="x")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    resp = await admin_client.put(
        "/api/v1/users/999999/role",
        json={"role_id": role.id},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 404


@pytest.mark.asyncio
async def test_update_user_role_unauthorized(
    auth_client: AsyncClient, db_session: Session
):
    """operator 尝试修改他人角色返回 40301。"""
    role = Role(name="r_unauth", description="x")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    user = User(
        username="role_target_op",
        hashed_password=get_password_hash("pass12345"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = await auth_client.put(
        f"/api/v1/users/{user.id}/role",
        json={"role_id": role.id},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40301


# ---------------------------------------------------------------------------
# 重复用户名 / 登录 / 密码哈希
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_with_existing_username(admin_client: AsyncClient):
    """重复用户名返回冲突 code 40901。"""
    await admin_client.post(
        "/api/v1/users",
        json={"username": "existuser", "password": "pass12345"},
    )
    resp = await admin_client.post(
        "/api/v1/users",
        json={"username": "existuser", "password": "pass12345"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40901


@pytest.mark.asyncio
async def test_login_with_wrong_password(client: AsyncClient, db_session: Session):
    """密码错误登录返回 code 40101。"""
    user = User(
        username="loginuser",
        hashed_password=get_password_hash("correctpass"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "loginuser", "password": "wrongpass"},
    )
    # 业务异常经全局处理后 HTTP 仍为 200，body code 为 40101
    assert resp.status_code == 200
    assert resp.json()["code"] == 40101


@pytest.mark.asyncio
async def test_create_user_password_hashed(
    admin_client: AsyncClient, db_session: Session
):
    """创建用户后数据库中存储的是哈希值，非明文。"""
    plain = "mysecret123"
    resp = await admin_client.post(
        "/api/v1/users",
        json={"username": "hashuser", "password": plain},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0

    u = db_session.execute(
        select(User).where(User.username == "hashuser")
    ).scalar_one()
    # 响应与库中均不含明文密码
    assert "password" not in resp.json()["data"]
    assert u.hashed_password != plain
    # 哈希值可通过 verify_password 校验
    assert verify_password(plain, u.hashed_password)
    assert not verify_password("notthepassword", u.hashed_password)
