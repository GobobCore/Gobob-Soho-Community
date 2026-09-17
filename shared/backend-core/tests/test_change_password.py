"""
test_change_password.py — POST /api/change-password + PATCH /api/profile 端点测试
======================================================================================

验证 (SaaS + 社区版通用):
1. POST /api/change-password — 提供旧密码正确 → 200 + 改成功
2. POST /api/change-password — 旧密码错 → 401
3. POST /api/change-password — 新密码 < 8 位 → 422
4. POST /api/change-password — 未鉴权 → 401
5. PATCH /api/profile — 改 name/phone/email/wechat 成功
6. PATCH /api/profile — None 字段不改 (PATCH 语义)
7. PATCH /api/profile — 未鉴权 → 401

R-Refactor 2026-09-17: SaaS 设置页增加个人资料 + 改密码功能
"""

import os

import pytest
import httpx


SOHO_BACKEND = os.environ.get("SOHO_TEST_BACKEND", "http://127.0.0.1:19001")
TEST_PASSWORD = "Admin#2026x"
TEST_NEW_PASSWORD = "NewPass#2026x"


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


@pytest.fixture
def token(client):
    """owner 登录拿 token + 用后还原."""
    r = client.post("/api/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _reset_password(client, token):
    """把 admin 密码改回原 TEST_PASSWORD (测试结束时还原)."""
    # 先试新密码登录 (避免旧密码已经改了但 token 还能用)
    r = client.post("/api/login", json={"username": "admin", "password": TEST_NEW_PASSWORD})
    if r.status_code == 200:
        tok = r.json()["token"]
        client.post(
            "/api/change-password",
            headers=_auth(tok),
            json={"old_password": TEST_NEW_PASSWORD, "new_password": TEST_PASSWORD},
        )


class TestChangePassword:
    def test_wrong_old_password_returns_401(self, client, token):
        r = client.post(
            "/api/change-password",
            headers=_auth(token),
            json={"old_password": "Wrong#2026x", "new_password": TEST_NEW_PASSWORD},
        )
        assert r.status_code == 401
        assert "旧密码" in r.json().get("detail", "")

    def test_too_short_new_password_returns_422(self, client, token):
        r = client.post(
            "/api/change-password",
            headers=_auth(token),
            json={"old_password": TEST_PASSWORD, "new_password": "short"},
        )
        assert r.status_code == 422

    def test_unauthenticated_returns_401(self, client):
        r = client.post(
            "/api/change-password",
            json={"old_password": TEST_PASSWORD, "new_password": TEST_NEW_PASSWORD},
        )
        assert r.status_code == 401

    def test_change_password_round_trip(self, client, token):
        """真改 + 真用新密码登录 + 还原."""
        try:
            # 1. 改密码
            r = client.post(
                "/api/change-password",
                headers=_auth(token),
                json={"old_password": TEST_PASSWORD, "new_password": TEST_NEW_PASSWORD},
            )
            assert r.status_code == 200, f"改密码失败: {r.text}"
            assert r.json() == {"changed": True}

            # 2. 用新密码登录应成功
            r2 = client.post("/api/login", json={
                "username": "admin", "password": TEST_NEW_PASSWORD,
            })
            assert r2.status_code == 200, f"新密码登录失败: {r2.text}"
            new_tok = r2.json()["token"]

            # 3. 用新登录 token 改回旧密码
            r3 = client.post(
                "/api/change-password",
                headers=_auth(new_tok),
                json={"old_password": TEST_NEW_PASSWORD, "new_password": TEST_PASSWORD},
            )
            assert r3.status_code == 200, f"还原失败: {r3.text}"
        except Exception:
            # 测试失败时强制还原
            _reset_password(client, token)
            raise

    def test_change_password_does_not_affect_other_sessions(self, client, token):
        """改密码不应撤销其他 session (业务决策: 不强制重登)."""
        try:
            # 留一个 token 留着, 改密码后再用
            r = client.post(
                "/api/change-password",
                headers=_auth(token),
                json={"old_password": TEST_PASSWORD, "new_password": TEST_NEW_PASSWORD},
            )
            assert r.status_code == 200
            # 旧 token 应仍然有效 (未撤销)
            r2 = client.get("/api/me", headers=_auth(token))
            # 业务决策: 返回 200 (旧 token 仍有效) 或 401 (撤销) 都行, 这里断言 200 (设计意图)
            assert r2.status_code == 200, f"旧 token 不应被撤销: {r2.status_code}"
            # 还原
            r3 = client.post(
                "/api/change-password",
                headers=_auth(token),
                json={"old_password": TEST_NEW_PASSWORD, "new_password": TEST_PASSWORD},
            )
            assert r3.status_code == 200
        except Exception:
            _reset_password(client, token)
            raise


class TestUpdateProfile:
    def test_update_name_phone_email(self, client, token):
        """PATCH 多字段成功."""
        try:
            # 取得原 name 以便还原
            r0 = client.get("/api/me", headers=_auth(token))
            orig_name = r0.json()["name"]

            r = client.patch(
                "/api/profile",
                headers=_auth(token),
                json={
                    "name": "admin (e2e update)",
                    "phone": "13900000000",
                    "email": "admin-test@example.com",
                },
            )
            assert r.status_code == 200, f"PATCH profile 失败: {r.text}"
            assert r.json()["updated"] == 3

            # GET /me 应看到新 name
            r2 = client.get("/api/me", headers=_auth(token))
            assert r2.json()["name"] == "admin (e2e update)"

            # 还原
            r3 = client.patch(
                "/api/profile",
                headers=_auth(token),
                json={"name": orig_name, "phone": "", "email": ""},
            )
            assert r3.status_code == 200
        except Exception:
            raise

    def test_patch_none_fields_no_change(self, client, token):
        """PATCH 不带字段 → 不改. updated 计数 = 0."""
        try:
            # PATCH 不带 phone 字段 (PATCH 语义), updated=0
            r = client.patch(
                "/api/profile",
                headers=_auth(token),
                json={},
            )
            assert r.status_code == 200
            assert r.json()["updated"] == 0

            # PATCH 只带 name 字段, updated=1
            r2 = client.patch(
                "/api/profile",
                headers=_auth(token),
                json={"name": "PATCH 语义测试"},
            )
            assert r2.status_code == 200
            assert r2.json()["updated"] == 1
        except Exception:
            raise

    def test_unauthenticated_returns_401(self, client):
        r = client.patch("/api/profile", json={"name": "unauth"})
        assert r.status_code == 401