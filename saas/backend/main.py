"""
cloud/backend-saas/main.py — SOHO SaaS 版 FastAPI 入口
=====================================================

SOHO SaaS 版 = shared/backend-core (业务核心) + SaaS 扩展 (saas_admin + billing + 多机构).

跟 community/backend/main.py 的区别:
- 多机构支持: portal ?org=demo-studio 分流, orgs.slug 识别
- SaaS 计费: 免费 2 协作账号, ≥3 每账号 ¥1000/年
- SaaS 运营后台 API: /api/saas/* (机构账户 / 账单 / 开源版订单 / 用量)
- 开源版按次购买集成: Gobob payment (alipay_pc)

启动: uvicorn main:app --port 19001
"""

import importlib.util
import logging
import os
import sys

# 路径: 加载 shared/backend-core 的 main.py (用 importlib 避免包名冲突)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SHARED_CORE = os.path.join(_REPO_ROOT, "shared", "backend-core")
_CLOUD_DIR = os.path.dirname(os.path.abspath(__file__))

# sys.path: shared 在前 (其内部模块 from core.X / from api.Y 能工作), cloud 在后
for p in (_CLOUD_DIR, _SHARED_CORE):
    if p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, _SHARED_CORE)
sys.path.append(_CLOUD_DIR)

# 加载 shared 的 main.py (工厂函数)
_shared_main_path = os.path.join(_SHARED_CORE, "main.py")
_spec = importlib.util.spec_from_file_location("soho.backend_core_main", _shared_main_path)
_shared_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared_main)
create_core_app = _shared_main.create_app

log = logging.getLogger("soho-saas")


def create_app():
    """SaaS 版 FastAPI app = shared 核心 + SaaS 扩展."""
    app = create_core_app()

    # ── SaaS 扩展路由 (用 importlib 加载本目录 saas_admin.py + billing.py) ──
    for _name, _file in (("cloud.saas_admin", "saas_admin.py"), ("cloud.saas_billing", "billing.py")):
        _path = os.path.join(_CLOUD_DIR, "api", _file)
        _spec2 = importlib.util.spec_from_file_location(_name, _path)
        _mod = importlib.util.module_from_spec(_spec2)
        _spec2.loader.exec_module(_mod)
        app.include_router(_mod.router)

    # TODO (Phase 2): 多机构路由 (portal ?org=demo-studio) — 已在 leads.py 改
    # TODO (Phase 2): 自助续费 / 升降级 — 后做

    return app


# uvicorn main:app 入口需要顶层 app
app = create_app()


# 直接 python3 -m cloud.backend_saas.main 也能跑 (调试用)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SOHO_BACKEND_PORT", "19001")))
