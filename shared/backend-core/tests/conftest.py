"""
conftest.py — pytest 配置
============================

让 shared/backend-core 内部的 from core.X / from api.Y / from main import ... 能正常 import.

R-Refactor 2026-09-16: SaaS/开源拆分后, 测试既能从 shared/ 跑, 也能从 community/ 跑.

R-Fix 2026-10-01: 原实现只把 tests/ 目录加进 sys.path (变量名却是 _BACKEND_CORE),
导致 `from main import create_app` 依赖其他测试文件先 import 的顺序副作用 ——
单独跑任一测试文件都会 ModuleNotFoundError: No module named 'main'。
这里改为把真正的 backend-core 根目录加入 sys.path。
"""
import sys
import os

# tests/ 的上一级才是 backend-core 根 (里面有 core/ api/ main.py)
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_CORE = os.path.dirname(_TESTS_DIR)

for _p in (_BACKEND_CORE, _TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
