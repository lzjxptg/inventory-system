"""示例测试：验证服务存活与统一异常体系正常。"""

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """健康检查接口无需鉴权即可访问。"""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_40101(client):
    """登录失败返回业务码 40101，HTTP 状态码为 200（统一响应约定）。"""
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody", "password": "wrong"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 40101
    assert "用户名或密码错误" in body["msg"]
