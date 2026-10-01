"""
test_shared_layer_boundaries.py — shared 层架构边界守护
=========================================================

R-Fix 2026-10-01 (P2 后续): 本次人工发现 shared/backend-core/api/orgs_me.py
硬查询 saas_api_usage / saas_key_orders / saas_invoices 三张 SaaS 专属表, 而这些
表由 saas/backend/api/saas_admin.py 运行时 DDL 创建、不在 shared 的 schema.sql 中
—— 社区部署里根本不存在, 调用该端点必然 500。

这类问题靠人读代码发现不可靠 (本次就漏了两周), 交给机器守。

## 规则

shared/backend-core 是社区版与 SaaS 版**共用**的业务核心, 因此:
  1. 代码里不得出现 saas_* 表名 —— 除非是显式声明的"能力探测"白名单
  2. 不得 import saas 侧模块 (cloud.* / saas.*)
  3. 社区入口注册的路由数里不得含 /api/saas (由 ci.yml 的 import check 兜底,
     此处再加一层, 让问题在本地 pytest 就能暴露)
"""

import os
import re
import sys

import pytest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_CORE = os.path.dirname(_TESTS_DIR)
_SHARED = os.path.dirname(_BACKEND_CORE)          # shared/
_SAAS_DIR = os.path.join(os.path.dirname(_SHARED), "saas")

# ── 允许引用 SaaS 表的位置 ────────────────────────────────────────────
# 形式: (相对 shared/backend-core 的路径, 允许出现的表名正则)
# 只有"先探测表是否存在、再决定是否查询"的地方才可放行 —— 单纯查询绝不允许。
_TABLE_PROBE_ALLOWLIST = {
    # orgs_me.py 用 _table_exists() 探测, 社区版整段跳过 (见 P2 修复)
    "api/orgs_me.py": re.compile(r"^(saas_api_usage|saas_key_orders|saas_invoices)$"),
}

_SAAS_TABLE_RX = re.compile(r"\bsaas_[a-z_]+\b")

# 不含测试文件与 __pycache__
def _iter_shared_py_files():
    for root, dirs, files in os.walk(_BACKEND_CORE):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "tests", ".pytest_cache")]
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


def _rel(path: str) -> str:
    return os.path.relpath(path, _BACKEND_CORE)


def _docstring_spans(src: str) -> list[tuple[int, int, int, int]]:
    """返回所有 docstring 的 (起行, 起列, 止行, 止列) 范围。

    只排除 docstring —— 不能笼统跳过所有字符串, 因为 SQL 里的表名
    (`"SELECT ... FROM saas_api_usage"`) 恰恰出现在字符串字面量中,
    那正是要检测的违规。
    """
    import ast

    spans = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return spans
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                spans.append((first.lineno, first.col_offset,
                              getattr(first, "end_lineno", first.lineno),
                              getattr(first, "end_col_offset", 0)))
    return spans


def _code_lines_with_token(path: str) -> list[tuple[int, str]]:
    """返回含 saas_* 标识符的"真实代码"行 (排除注释与 docstring)。

    用 tokenize 区分注释/字符串, 再用 ast 精确排除 docstring ——
    单纯的正则或"跳过所有字符串"都会误判:
      - 正则: 把 docstring 里的用法说明当成依赖 (main.py 即如此)
      - 跳过全部字符串: 把 SQL 里的真实表名引用漏掉 (本次即栽在这)
    """
    import io
    import tokenize

    src = open(path, encoding="utf-8", errors="ignore").read()
    lines = src.splitlines()
    spans = _docstring_spans(src)

    def in_docstring(tok) -> bool:
        return any(tok.start[0] == s[0] and tok.start[1] >= s[1]
                   for s in spans)

    hits: list[tuple[int, str]] = []
    with open(path, "rb") as fh:
        try:
            tokens = list(tokenize.tokenize(io.BytesIO(
                src.encode("utf-8")).readline))
        except (tokenize.TokenError, SyntaxError):
            return hits
    for tok in tokens:
        if tok.type in (tokenize.COMMENT,):
            continue
        if not _SAAS_TABLE_RX.search(tok.string):
            continue
        if in_docstring(tok):
            continue
        ln = tok.start[0]
        text = lines[ln - 1].strip() if 0 < ln <= len(lines) else tok.string
        hits.append((ln, text))
    return hits


@pytest.mark.skipif(not os.path.isdir(_SAAS_DIR), reason="非 monorepo 布局, 跳过")
class TestNoSaasTableLeak:
    """规则 1: shared 层不得硬依赖 SaaS 专属表。"""

    def test_no_saas_table_outside_allowlist(self):
        offenders = []
        for path in _iter_shared_py_files():
            rel = _rel(path)
            allowed = _TABLE_PROBE_ALLOWLIST.get(rel)
            for lineno, text in _code_lines_with_token(path):
                for m in _SAAS_TABLE_RX.finditer(text):
                    name = m.group(0)
                    if allowed and allowed.match(name):
                        continue
                    offenders.append(f"{rel}:{lineno}  {text[:90]}")
        assert not offenders, (
            "shared 层出现 SaaS 专属表引用 —— 社区版部署时这些表不存在:\n  "
            + "\n  ".join(offenders)
            + "\n\n如确需按能力探测, 请加入 _TABLE_PROBE_ALLOWLIST 并确保"
              "查询前先判断表存在。"
        )

    def test_allowlisted_files_actually_probe(self):
        """白名单不能变成"什么都往里塞"的万能洞。"""
        for rel, rx in _TABLE_PROBE_ALLOWLIST.items():
            path = os.path.join(_BACKEND_CORE, rel)
            assert os.path.isfile(path), f"白名单指向不存在的文件: {rel}"
            src = open(path, encoding="utf-8", errors="ignore").read()
            assert "_table_exists" in src, (
                f"{rel} 在白名单中但未见 _table_exists 探测 —— "
                "白名单应只放行'探测后条件查询'的用法"
            )


@pytest.mark.skipif(not os.path.isdir(_SAAS_DIR), reason="非 monorepo 布局, 跳过")
class TestNoSaasImport:
    """规则 2: shared 层不得 import SaaS 侧模块。"""

    def test_no_cloud_import(self):
        offenders = []
        for path in _iter_shared_py_files():
            src = open(path, encoding="utf-8", errors="ignore").read()
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.search(r"\bfrom\s+cloud\b", stripped) or \
                   re.search(r"\bimport\s+cloud\b", stripped) or \
                   re.search(r"\bimport_module\(['\"]cloud", stripped):
                    offenders.append(f"{_rel(path)}:{lineno}  {stripped[:90]}")
        assert not offenders, (
            "shared 层 import 了 SaaS 侧模块:\n  " + "\n  ".join(offenders)
        )


@pytest.mark.skipif(not os.path.isdir(_SAAS_DIR), reason="非 monorepo 布局, 跳过")
class TestCommunityEntryStaysClean:
    """规则 3: 社区入口不得挂上 SaaS 路由。"""

    def test_community_app_has_no_saas_routes(self):
        if _BACKEND_CORE not in sys.path:
            sys.path.insert(0, _BACKEND_CORE)
        community_backend = os.path.join(
            os.path.dirname(_SHARED), "community", "backend"
        )
        if not os.path.isdir(community_backend):
            pytest.skip("无 community/backend 目录")
        if community_backend not in sys.path:
            sys.path.append(community_backend)
        from main import create_app  # noqa: E402

        app = create_app()
        saas_routes = [r for r in app.routes if "/api/saas" in str(r.path)]
        assert not saas_routes, (
            f"社区入口不应有 SaaS 路由, 但发现 {len(saas_routes)} 条: "
            f"{[str(r.path) for r in saas_routes[:5]]}"
        )
