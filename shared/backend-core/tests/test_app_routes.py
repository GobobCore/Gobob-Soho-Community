"""
test_app_routes.py — 后端整体路由测试
======================================

不连 DB, 验证:
- create_app() 能跑通
- 关键路由都注册了
- community 入口不含 SaaS 路由
- 路由 method/path 正确
"""

import sys
import os
import pytest

# 加路径让 import main 可工作
_BACKEND_CORE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_CORE not in sys.path:
    sys.path.insert(0, _BACKEND_CORE)


class TestCommunityApp:
    """社区版入口 (community/backend/main.py) - 无 SaaS 路由."""

    @pytest.fixture(autouse=True)
    def setup_path(self):
        """加 community/backend 到 sys.path."""
        community_backend = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'community', 'backend'
        )
        if community_backend not in sys.path:
            sys.path.append(community_backend)
        yield
        # cleanup
        if community_backend in sys.path:
            sys.path.remove(community_backend)

    def test_community_routes_count(self):
        """社区版应 85 业务路由."""
        from main import create_app
        app = create_app()
        assert len(app.routes) >= 80, f"社区版路由数 {len(app.routes)} 太少, 应 ≥ 80"

    def test_community_no_saas_routes(self):
        """社区版不应有 /api/saas/* 路由."""
        from main import create_app
        app = create_app()
        saas = [r for r in app.routes if '/api/saas' in str(r.path)]
        assert saas == [], f"社区版有 SaaS 路由: {[str(r.path) for r in saas]}"

    def test_community_has_key_routes(self):
        """社区版业务路由必须存在."""
        from main import create_app
        app = create_app()
        paths = {str(r.path) for r in app.routes}
        required = [
            '/api/health',
            '/api/login',
            '/api/me',
            '/api/register',
            '/api/leads/capture',
        ]
        for r in required:
            assert r in paths, f"缺失关键路由 {r}"

    def test_health_endpoint_no_auth(self):
        """/api/health 不需要鉴权."""
        from fastapi.testclient import TestClient
        from main import create_app
        app = create_app()
        client = TestClient(app)
        resp = client.get("/api/health")
        # 200 或 503 (db 连接) 都可, 但不应 401
        assert resp.status_code != 401
        assert resp.status_code in (200, 503)


class TestSharedCoreApp:
    """shared/backend-core/main.py — 业务核心 create_app()."""

    def test_create_app_returns_fastapi(self):
        sys.path.insert(0, _BACKEND_CORE)
        from main import create_app
        app = create_app()
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_top_level_app_routes(self):
        """顶层 main.app (供 uvicorn main:app 跑)."""
        sys.path.insert(0, _BACKEND_CORE)
        import main
        # 顶层 app 应已 create 完
        assert hasattr(main, 'app')
        assert len(main.app.routes) >= 80
