"""
shared/backend-core/main.py — SOHO 业务核心 FastAPI 工厂
=====================================================

提供 `create_app()` 函数, 返回 FastAPI 实例, 挂载业务核心路由:
  leads / contracts / students / assignments / workflow / templates / messages / dashboard

community/backend/main.py 和 cloud/backend-saas/main.py 都从这儿 create_app(),
各自再加自己的扩展 router (community 不加, cloud 加 saas_admin/billing 等).

R-Refactor 2026-09-16: SaaS/开源拆分 — 业务核心抽出到 shared/, 两版共享.
"""

import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 让 import shared.backend-core.* 可用 (community/backend 或 cloud/backend-saas 调用时,
# 把 shared/backend-core 加到 sys.path, 这样内部的 from core.X / from api.Y 都能工作)
_BACKEND_CORE = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_CORE not in sys.path:
    sys.path.insert(0, _BACKEND_CORE)

from core.config import get_settings  # noqa: E402
from core.database import db_cursor  # noqa: E402
from core import auth  # noqa: E402
from core.id_gen import new_id  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("soho-core")
settings = get_settings()


def _bootstrap():
    """首次启动：建初始机构 + 管理员（幂等）。建表由 deploy 的 schema.sql 负责。"""
    if not settings.admin_password:
        log.warning("SOHO_ADMIN_PASSWORD 未设置，跳过初始管理员创建")
        return
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM orgs")
        if cur.fetchone()["c"] > 0:
            return  # 已初始化
        org_id = new_id()
        cur.execute("INSERT INTO orgs (id, name) VALUES (%s, %s)", (org_id, settings.org_name))
        acc_id = new_id()
        cur.execute(
            "INSERT INTO accounts (id, username, password_hash, org_id) VALUES (%s, %s, %s, %s)",
            (acc_id, settings.admin_username, auth.hash_password(settings.admin_password), org_id),
        )
        cur.execute(
            "INSERT INTO members (id, account_id, org_id, name, role) VALUES (%s, %s, %s, %s, %s)",
            (new_id(), acc_id, org_id, settings.admin_username, auth.ROLE_OWNER),
        )
        # 把 default 的 pipeline 阶段（org_id='default' 的种子）复制到本机构, 保留 default 不动
        # (后续自助注册要从 default 复制, 不能 UPDATE 把 default 搬空)
        cur.execute(
            "INSERT INTO lead_pipeline_stages (stage_id, org_id, name, sort_order, is_start, is_won, is_lost, max_days) "
            "SELECT stage_id, %s, name, sort_order, is_start, is_won, is_lost, max_days "
            "FROM lead_pipeline_stages WHERE org_id='default'",
            (org_id,),
        )
        log.info("初始化完成：机构 '%s' + 管理员 '%s' + pipeline 阶段 %d",
                 settings.org_name, settings.admin_username, cur.rowcount)


def create_app() -> FastAPI:
    """FastAPI 工厂 — 返回业务核心 app (不含 SaaS 扩展).

    cloud/backend-saas/main.py 用法:
        from shared.backend_core.main import create_app
        app = create_app()
        app.include_router(saas_admin_router)  # SaaS 扩展
        return app
    """
    app = FastAPI(title="Gobob SOHO API", version="0.2.0", redirect_slashes=True)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 开源自托管场景，前端端口随部署变化；生产建议收敛
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        """健康检查 + Gobob 数据 API 连通性（不泄露 Key）。"""
        from core import gobob_client
        db_ok = True
        try:
            with db_cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except Exception as e:
            db_ok = False
            log.error("health db check: %s", e)
        return {
            "ok": db_ok,
            "service": "gobob-soho-core",
            "db": "up" if db_ok else "down",
            "gobob_data_api": "configured" if gobob_client.is_enabled() else "disabled",
        }

    @app.on_event("startup")
    def startup():
        try:
            _bootstrap()
        except Exception as e:
            log.warning("bootstrap 跳过（表可能未建，先跑 schema.sql）: %s", e)

    # ── 业务核心路由挂载 ──
    from api import (  # noqa: E402
        assessment, auth_router, assignments, contracts, dashboard,
        leads, messages, orgs_me, relationships, reports, staff, students, templates, workflow,
    )

    for _r in (auth_router, assessment, leads, contracts, assignments, students,
               workflow, templates, staff, dashboard, messages, orgs_me, relationships, reports):
        app.include_router(_r.router)

    return app


# uvicorn main:app 入口需要顶层 app
app = create_app()


# 直接 python3 -m shared.backend_core.main 也能跑 (调试用)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SOHO_BACKEND_PORT", "19001")))
