"""
conftest.py — pytest 配置
============================

让 shared/backend-core 内部的 from core.X / from api.Y 能正常 import.

R-Refactor 2026-09-16: SaaS/开源拆分后, 测试既能从 shared/ 跑, 也能从 community/ 跑.
"""
import sys
import os

_BACKEND_CORE = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_CORE not in sys.path:
    sys.path.insert(0, _BACKEND_CORE)
