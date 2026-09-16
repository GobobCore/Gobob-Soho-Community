"""
test_integration_e2e.py — SOHO 端到端集成测试
==============================================

测真服务 (本机 19001 backend 已经在跑), 用 httpx 发真 HTTP 请求.

测什么:
1. 健康检查 (/api/health)
2. 公开评估元数据 (/api/assessment/meta) - 匿名可用
3. SaaS 运营登录 (19001/api/saas/login) - 拿 token
4. 机构列表 (19001/api/saas/orgs) - SaaS 多机构
5. 开源版按次购买 (19001/api/saas/buy-key) - 公开, 走 Gobob payment
6. 评估匹配 (19001/api/assessment/match) - 匿名

R-Feat 2026-09-16: 端到端用真服务测, 确保拆分后整个 SaaS + 开源版链路通.

注意: 这些测试需要真 backend 跑 (19001), 不连 = skip.
"""

import os
import time
import uuid

import pytest
import httpx


# ── 配置 ──
SOHO_BACKEND = os.environ.get("SOHO_TEST_BACKEND", "http://127.0.0.1:19001")
OPS_PASSWORD = os.environ.get("SOHO_TEST_OPS_PASSWORD", "SOHOps#2026x")


def _service_reachable(url: str, timeout: float = 2.0) -> bool:
    try:
        r = httpx.get(f"{url}/api/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


# Skip 全部如果 backend 不在 (CI 上 backend 可能没起)
pytestmark = pytest.mark.skipif(
    not _service_reachable(SOHO_BACKEND),
    reason=f"backend {SOHO_BACKEND} 不可达, 跳过 integration test",
)


@pytest.fixture
def client():
    """httpx.Client 共享 session, 加速测试."""
    return httpx.Client(base_url=SOHO_BACKEND, timeout=15.0)


# ── 1. 健康检查 ──

class TestHealth:
    def test_health_endpoint(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["db"] == "up"
        # service 字段反映 SaaS 入口
        assert "gobob-soho" in data["service"] or "gobob-soho-core" in data["service"]


# ── 2. 智能评估 (匿名公开) ──

class TestAssessmentPublic:
    def test_meta_returns_real_data(self, client):
        """meta 端点应返真 Gobob Data API 数据 (前提是配置了 Key)."""
        r = client.get("/api/assessment/meta")
        # 503 = Key 没配; 200 = 有数据. CI 上可能没配, 容错
        if r.status_code == 503:
            pytest.skip("Gobob Data API Key 未配置, 跳过")
        assert r.status_code == 200
        data = r.json()
        assert "countries" in data
        assert len(data["countries"]) >= 1
        # 至少有中国 / 美国
        country_ids = {c.get("country_id") or c.get("iso_code") for c in data["countries"]}
        assert "US" in country_ids or "CN" in country_ids


# ── 3. SaaS 运营登录 ──

class TestOpsLogin:
    def test_ops_login_success(self, client):
        r = client.post("/api/saas/login", json={
            "username": "zeke",
            "password": OPS_PASSWORD,
        })
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["admin"]["username"] == "zeke"

    def test_ops_login_wrong_password(self, client):
        r = client.post("/api/saas/login", json={
            "username": "zeke",
            "password": "wrong",
        })
        assert r.status_code == 401


# ── 4. 机构列表 (SaaS 多机构) ──

class TestOrgsList:
    def test_orgs_requires_auth(self, client):
        r = client.get("/api/saas/orgs")
        assert r.status_code == 401

    def test_orgs_list_with_token(self, client):
        # 拿 token
        login = client.post("/api/saas/login", json={
            "username": "zeke",
            "password": OPS_PASSWORD,
        }).json()
        token = login["token"]
        # 查机构
        r = client.get("/api/saas/orgs", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        # 至少有 1 个机构 (测试留学工作室)
        assert data["summary"]["total_orgs"] >= 1

    def test_org_detail(self, client):
        login = client.post("/api/saas/login", json={
            "username": "zeke",
            "password": OPS_PASSWORD,
        }).json()
        token = login["token"]
        # 查第一个机构
        orgs = client.get("/api/saas/orgs", headers={"Authorization": f"Bearer {token}"}).json()
        if not orgs["items"]:
            pytest.skip("没机构")
        org_id = orgs["items"][0]["id"]
        r = client.get(
            f"/api/saas/orgs/{org_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "org" in data
        assert "invoices" in data
        assert "usage_30d" in data


# ── 5. 开源版按次购买 (公开 + SaaS 运营后台) ──

class TestBuyKey:
    def test_buy_key_create_order(self, client):
        """公开: 任何人都能下单 buy-key."""
        r = client.post("/api/saas/buy-key", json={
            "org_name": f"E2E 集成测试 {uuid.uuid4().hex[:6]}",
            "contact_name": "集成测试",
            "contact_email": f"e2e-{uuid.uuid4().hex[:6]}@test.com",
            "calls": 50,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert "order_no" in data
        assert data["calls"] == 50
        assert data["amount"] == 50.0  # 50 次 * ¥1

    def test_buy_key_status_check(self, client):
        """下完单能查 status (公开端点)."""
        order = client.post("/api/saas/buy-key", json={
            "org_name": f"E2E check {uuid.uuid4().hex[:6]}",
            "contact_name": "check",
            "contact_email": f"check-{uuid.uuid4().hex[:6]}@test.com",
            "calls": 10,
        }).json()
        order_no = order["order_no"]
        r = client.get(f"/api/saas/buy-key/{order_no}")
        assert r.status_code == 200
        data = r.json()
        assert data["order_no"] == order_no
        assert data["status"] == "pending"  # 未付时是 pending

    def test_buy_key_invalid_count(self, client):
        """calls < 10 应被 pydantic 校验拦 (422, ge=10 约束)."""
        r = client.post("/api/saas/buy-key", json={
            "org_name": "bad",
            "contact_name": "bad",
            "contact_email": "bad@bad.com",
            "calls": 5,  # 太小, pydantic ge=10 应拦
        })
        # pydantic 校验失败返 422 Unprocessable Entity
        assert r.status_code in (400, 422)


# ── 6. 评估匹配 (匿名) ──

class TestAssessmentMatch:
    def test_match_with_real_gobob(self, client):
        """真评估: gpa=3.5 + target US, 应得至少 1 个学校."""
        r = client.post("/api/assessment/match", json={
            "form": {
                "gpa": 3.5,
                "toefl": 100,
                "target_countries": ["US"],
                "current_stage": "undergraduate",
                "target_degree": "Master",
            }
        })
        # 503 = Key 没配; 其他 = 跑了
        if r.status_code == 503:
            pytest.skip("Gobob Key 未配, 跳过")
        if r.status_code == 502:
            pytest.skip(f"远程服务暂时不可用: {r.text[:100]}")
        assert r.status_code == 200
        data = r.json()
        assert "matches" in data
        # 至少返一些匹配
        assert data["total"] >= 1
