"""
backend/main.py — Gobob SOHO API 入口

纯 API 服务。业务路由在 api/ 下逐步挂载。
首次启动：幂等建表 + 创建初始机构与管理员。
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import db_cursor
from core import auth
from core.id_gen import new_id

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("soho")
settings = get_settings()

app = FastAPI(title="Gobob SOHO API", version="0.1.0", redirect_slashes=True)

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
        "service": "gobob-soho",
        "db": "up" if db_ok else "down",
        "gobob_data_api": "configured" if gobob_client.is_enabled() else "disabled",
    }


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
        # 把默认 pipeline 阶段（org_id='default' 的种子）绑定到本机构
        cur.execute(
            "UPDATE lead_pipeline_stages SET org_id=%s WHERE org_id='default'",
            (org_id,),
        )
        log.info("初始化完成：机构 '%s' + 管理员 '%s'", settings.org_name, settings.admin_username)


@app.on_event("startup")
def startup():
    try:
        _bootstrap()
    except Exception as e:
        log.warning("bootstrap 跳过（表可能未建，先跑 schema.sql）: %s", e)


# ── 路由挂载 ──
from api import (  # noqa: E402
    assessment, auth_router, assignments, contracts, dashboard,
    leads, messages, relationships, reports, staff, students, templates, workflow,
)

for _r in (auth_router, assessment, leads, contracts, assignments, students,
           workflow, templates, staff, dashboard, messages, relationships, reports):
    app.include_router(_r.router)
