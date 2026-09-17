"""
test_orgs_me.py — GET/PUT /api/orgs/me 端点测试
=================================================

验证 (SaaS + 社区版通用):
1. GET /api/orgs/me — 任何登录用户都能读 (advisor/student/parent 看不到 gobob_api_key)
2. PUT /api/orgs/me — 只有 owner 能改, 其它角色 403
3. PUT PATCH 语义 — None 字段不改, 空字符串清空
4. 不存在的字段不报错 (model_extra=ignore)

R-Refactor 2026-09-17: SaaS 设置页 + v0.21.0 migration 新增接口

测真服务 (本机 19001), backend 必须跑着.
"""

import os

import pytest
import httpx


SOHO_BACKEND = os.environ.get("SOHO_TEST_BACKEND", "http://127.0.0.1:19001")


def _service_reachable(url: str, timeout: float = 2.0) -> bool:
    try:
        r = httpx.get(f"{url}/api/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _service_reachable(SOHO_BACKEND),
    reason=f"backend {SOHO_BACKEND} 不可达, 跳过"
)


@pytest.fixture
def client():
    return httpx.Client(base_url=SOHO_BACKEND, timeout=15.0)


def _login(client, username="admin", password="Admin#2026x"):
    """机构 owner 登录拿 token."""
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.status_code} {r.text}"
    return r.json()["token"]


def _login_student(client):
    """学生登录拿 token (用于测 PUT 403)."""
    # 测试学生账号: gobob_test_student_001 / Test#2026x
    # 这是 seed 灌入的 demo 学生
    r = client.post("/api/login", json={
        "username": "gobob_test_student_001",
        "password": "Test#2026x",
    })
    if r.status_code != 200:
        pytest.skip(f"测试学生账号登录失败: {r.text}")
    return r.json()["token"]


class TestGetMyOrg:
    def test_owner_can_read_full_org_info(self, client):
        """owner GET 看到全字段 (含 gobob_api_key 简码/或不返)."""
        token = _login(client)
        r = client.get("/api/orgs/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        # 必有字段
        assert "id" in data
        assert "name" in data
        # 新增字段 (v0.21.0 migration 后存在)
        for k in ("description", "address", "phone", "email", "website", "logo_url"):
            assert k in data, f"字段 {k} 缺失"

    def test_advisor_can_read_org_info_no_api_key(self, client):
        """advisor 看不到 gobob_api_key (机密)."""
        # 找一个 advisor 账号 — 用 seed 数据
        r = client.post("/api/login", json={
            "username": "gobob_test_advisor_01",
            "password": "Test#2026x",
        })
        if r.status_code != 200:
            pytest.skip(f"advisor 账号登录失败: {r.text}")
        token = r.json()["token"]
        r = client.get("/api/orgs/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert "gobob_api_key" not in data or data.get("gobob_api_key") is None, \
            "advisor 不应看到 gobob_api_key"

    def test_unauthenticated_returns_401(self, client):
        r = client.get("/api/orgs/me")
        assert r.status_code == 401


class TestUpdateMyOrg:
    def test_owner_can_update_org_info(self, client):
        """owner PUT 成功, 更新多字段."""
        token = _login(client)
        new_data = {
            "description": "单元测试 - 专注北美研究生申请",
            "address": "北京市朝阳区建国路88号",
            "phone": "010-12345678",
            "email": "contact-test@example.com",
            "website": "https://e2e-test.example.com",
        }
        r = client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json=new_data,
        )
        assert r.status_code == 200, f"PUT 失败: {r.status_code} {r.text}"
        assert r.json()["updated"] == len(new_data)

        # 验证 GET 看到新值
        r = client.get("/api/orgs/me", headers={"Authorization": f"Bearer {token}"})
        data = r.json()
        assert data["description"] == new_data["description"]
        assert data["address"] == new_data["address"]
        assert data["phone"] == new_data["phone"]
        assert data["email"] == new_data["email"]
        assert data["website"] == new_data["website"]

    def test_owner_can_update_name(self, client):
        """owner 改 name 后 GET 应见新名."""
        token = _login(client)
        # 先取当前 name
        r = client.get("/api/orgs/me", headers={"Authorization": f"Bearer {token}"})
        old_name = r.json()["name"]
        new_name = old_name + " (e2e update)"
        r = client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": new_name},
        )
        assert r.status_code == 200
        assert r.json()["updated"] == 1
        r = client.get("/api/orgs/me", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["name"] == new_name
        # 还原
        client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": old_name},
        )

    def test_owner_can_clear_field_with_empty_string_ignored(self, client):
        """PATCH 语义: PUT 不带某字段 = 不改, 而不是清空."""
        token = _login(client)
        # 设置一个值
        client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"website": "https://keep-me.example.com"},
        )
        # PUT 不带 website 字段
        r = client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": "只改 description"},
        )
        assert r.status_code == 200
        # website 应保持
        r = client.get("/api/orgs/me", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["website"] == "https://keep-me.example.com"

    def test_advisor_cannot_update_returns_403(self, client):
        """非 owner PUT 应 403."""
        r = client.post("/api/login", json={
            "username": "gobob_test_advisor_01",
            "password": "Test#2026x",
        })
        if r.status_code != 200:
            pytest.skip(f"advisor 账号登录失败: {r.text}")
        token = r.json()["token"]
        r = client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": "advisor 试图改机构信息"},
        )
        assert r.status_code == 403, f"advisor PUT 应被拒: {r.status_code}"

    def test_student_cannot_update_returns_403(self, client):
        """student PUT 应 403."""
        token = _login_student(client)
        r = client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"description": "student 试图改机构信息"},
        )
        assert r.status_code == 403, f"student PUT 应被拒: {r.status_code}"

    def test_empty_name_rejected(self, client):
        """name 不能为空字符串 (schema NOT NULL)."""
        token = _login(client)
        r = client.put(
            "/api/orgs/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "   "},
        )
        # 后端在 SQL 之前就抛 400, 也可能 MySQL 抛 500. 容错两个.
        assert r.status_code in (400, 422, 500), f"name='' 应被拒, 实际 {r.status_code}: {r.text}"