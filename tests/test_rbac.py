"""RBAC 权限模块测试。

覆盖角色 CRUD、权限列表、角色权限分配、当前用户信息与权限查询、
用户角色分配，以及基于角色的接口访问控制。
所有测试在独立事务中运行，结束后自动回滚。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import get_password_hash
from models.role import Permission, Role, RolePermission
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


@pytest.fixture
def setup_roles_perms(db_session: Session):
    """预置一个角色与若干权限，返回 role 和 perm 列表。"""
    role = Role(name="tester", description="测试角色")
    db_session.add(role)
    db_session.flush()
    perms = [
        Permission(code="purchase:view", name="查看采购", module="purchase"),
        Permission(code="purchase:create", name="创建采购", module="purchase"),
    ]
    db_session.add_all(perms)
    db_session.flush()
    db_session.commit()
    db_session.refresh(role)
    return {"role": role, "perms": perms}


# ---------------------------------------------------------------------------
# 角色 CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_roles(auth_client: AsyncClient, db_session: Session):
    """角色列表接口返回正常。"""
    db_session.add(Role(name="role_a", description="a"))
    db_session.commit()

    resp = await auth_client.get("/api/v1/roles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)
    assert any(r["name"] == "role_a" for r in body["data"])


@pytest.mark.asyncio
async def test_create_role_admin_only(
    admin_client: AsyncClient, db_session: Session
):
    """admin 可创建角色，重复 name 返回 400。"""
    resp = await admin_client.post(
        "/api/v1/roles",
        json={"name": "newrole", "description": "新角色"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "newrole"

    # 重复 name
    resp2 = await admin_client.post(
        "/api/v1/roles",
        json={"name": "newrole", "description": "重复"},
    )
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_create_role_operator_forbidden(auth_client: AsyncClient):
    """operator（默认角色）创建角色应返回 40301。"""
    resp = await auth_client.post(
        "/api/v1/roles",
        json={"name": "oprole", "description": "操作员尝试创建"},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40301


@pytest.mark.asyncio
async def test_update_role(admin_client: AsyncClient, db_session: Session):
    """admin 可更新角色。"""
    role = Role(name="updro", description="old")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    resp = await admin_client.put(
        f"/api/v1/roles/{role.id}",
        json={"description": "new"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "new"


@pytest.mark.asyncio
async def test_delete_role(admin_client: AsyncClient, db_session: Session):
    """admin 可逻辑删除角色。"""
    role = Role(name="delrole", description="to delete")
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    resp = await admin_client.delete(f"/api/v1/roles/{role.id}")
    assert resp.status_code == 200

    # 数据库中 is_deleted=1
    r = db_session.execute(
        select(Role).where(Role.id == role.id)
    ).scalar_one()
    assert r.is_deleted == 1


# ---------------------------------------------------------------------------
# 权限列表
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_permissions(auth_client: AsyncClient, db_session: Session):
    """权限列表接口正常返回。"""
    db_session.add(Permission(code="x:y", name="x", module="x"))
    db_session.commit()

    resp = await auth_client.get("/api/v1/permissions")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert any(p["code"] == "x:y" for p in resp.json()["data"])


# ---------------------------------------------------------------------------
# 角色权限分配
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_role_permission_ids(
    auth_client: AsyncClient, setup_roles_perms: dict, db_session: Session
):
    """查询角色已分配权限 ID 列表。"""
    role = setup_roles_perms["role"]
    perms = setup_roles_perms["perms"]
    db_session.add(RolePermission(role_id=role.id, permission_id=perms[0].id))
    db_session.commit()

    resp = await auth_client.get(f"/api/v1/roles/{role.id}/permissions")
    assert resp.status_code == 200
    assert perms[0].id in resp.json()["data"]


@pytest.mark.asyncio
async def test_assign_role_permissions(
    admin_client: AsyncClient, setup_roles_perms: dict, db_session: Session
):
    """admin 可分配角色权限（全量覆盖）。"""
    role = setup_roles_perms["role"]
    perms = setup_roles_perms["perms"]

    resp = await admin_client.put(
        f"/api/v1/roles/{role.id}/permissions",
        json={"permission_ids": [p.id for p in perms]},
    )
    assert resp.status_code == 200

    # 校验数据库关联
    rows = db_session.execute(
        select(RolePermission).where(RolePermission.role_id == role.id)
    ).scalars().all()
    assert len(rows) == len(perms)


# ---------------------------------------------------------------------------
# /me 与 /me/permissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me(auth_client: AsyncClient):
    """GET /roles/me 返回当前用户信息含 role 字段。"""
    resp = await auth_client.get("/api/v1/roles/me")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["username"] == "testuser"
    # 默认 operator
    assert data["role"] == "operator"


@pytest.mark.asyncio
async def test_get_me_permissions(auth_client: AsyncClient, db_session: Session):
    """GET /roles/me/permissions 返回权限 code 列表。"""
    # 默认 operator 角色，无预置权限，应为空
    resp = await auth_client.get("/api/v1/roles/me/permissions")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_get_me_permissions_admin(
    admin_client: AsyncClient, db_session: Session
):
    """admin 用户的 /me/permissions 返回其角色权限。"""
    # 为 admin 角色分配一个权限
    admin_role = db_session.execute(
        select(Role).where(Role.name == "admin")
    ).scalar_one()
    perm = Permission(code="role:manage", name="角色管理", module="settings")
    db_session.add(perm)
    db_session.flush()
    db_session.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
    db_session.commit()

    resp = await admin_client.get("/api/v1/roles/me/permissions")
    assert resp.status_code == 200
    assert "role:manage" in resp.json()["data"]


# ---------------------------------------------------------------------------
# 用户角色分配
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_user_role(
    admin_client: AsyncClient, db_session: Session
):
    """admin 可为用户分配角色。"""
    role = Role(name="assign_target", description="target")
    db_session.add(role)
    db_session.flush()
    user = User(
        username="assignee",
        hashed_password=get_password_hash("pass12345"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(role)
    db_session.refresh(user)

    resp = await admin_client.put(
        f"/api/v1/users/{user.id}/role",
        json={"role_id": role.id},
    )
    assert resp.status_code == 200

    u = db_session.execute(select(User).where(User.id == user.id)).scalar_one()
    assert u.role_id == role.id


@pytest.mark.asyncio
async def test_assign_user_role_operator_forbidden(
    auth_client: AsyncClient, db_session: Session
):
    """operator 分配用户角色应返回 40301。"""
    role = Role(name="forbid_role", description="f")
    db_session.add(role)
    db_session.flush()
    user = User(
        username="forbid_user",
        hashed_password=get_password_hash("pass12345"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(role)
    db_session.refresh(user)

    resp = await auth_client.put(
        f"/api/v1/users/{user.id}/role",
        json={"role_id": role.id},
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 40301
