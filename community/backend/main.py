"""
community/backend/main.py — SOHO 开源社区版 FastAPI 入口
=====================================================

SOHO 开源版 (单机构自托管) = shared/backend-core (业务核心), 无 SaaS 扩展.

跟 cloud/backend-saas/main.py 的区别:
- 单机构: org_id 从 env 读 (SOHO_ORG_ID, 默认 default_org), 无多机构路由
- 无计费: 没有 SaaS 订阅, 没有开源版按次购买 (那是 SaaS 运营版的事)
- 无 SaaS 运营后台: /api/saas/* 不在开源版

启动: uvicorn main:app --port 19013
"""

import logging
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SHARED_CORE = os.path.join(_REPO_ROOT, "shared", "backend-core")
_CLOUD_DIR = os.path.dirname(os.path.abspath(__file__))
# 顺序: shared 在前 (因为它的 main.py 是工厂), community 在后
for p in (_CLOUD_DIR, _SHARED_CORE):
    if p in sys.path:
        sys.path.remove(p)
sys.path.insert(0, _SHARED_CORE)
sys.path.append(_CLOUD_DIR)

# 加载 shared 的 main (用 importlib 避免包名冲突)
import importlib.util  # noqa: E402
_shared_main_path = os.path.join(_SHARED_CORE, "main.py")
_spec = importlib.util.spec_from_file_location("soho.backend_core_main", _shared_main_path)
_shared_main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared_main)
create_core_app = _shared_main.create_app

log = logging.getLogger("soho-community")


def create_app():
    """开源版 FastAPI app = shared 核心, 无 SaaS 扩展."""
    return create_core_app()


# uvicorn main:app 入口需要顶层 app
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SOHO_BACKEND_PORT", "19013")))
