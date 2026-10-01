"""
test_orgs_me_usage_degrade.py — /api/orgs/me/usage 的社区版降级保证
=========================================================================

R-Fix 2026-10-01 (P2): 本模块属于 shared 层, 社区版与 SaaS 版共用。但
saas_api_usage / saas_key_orders / saas_invoices 三张表只在
saas/backend/api/saas_admin.py 里用运行时 DDL 创建, 不在 shared 的
schema.sql 中 —— 社区部署里这三张表根本不存在。

改造前该端点无条件查这三张表, 社区版调用必然 500 (table doesn't exist)。
改造后按表存在性探测, 缺失则跳过并返回 billing_available=false。

这里用 fake cursor 记录**实际执行了哪些 SQL**, 断言社区版路径下
不出现任何 saas_* 表访问 —— 这比打真实服务更精确, 也不需要起 DB。
"""

import sys
import os

import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_CORE = os.path.dirname(_TESTS_DIR)
for _p in (_BACKEND_CORE, _TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import orgs_me  # noqa: E402


class FakeCursor:
    """记录 SQL 的假 cursor, 并对已知表返回最小可用结果集."""

    def __init__(self, existing_tables: set[str]):
        self.existing = set(existing_tables)
        self.executed: list[str] = []
        self._rows: list[dict] = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if "information_schema.tables" in sql:
            table = (params or ("",))[0]
            self._rows = [{"c": 1}] if table in self.existing else []
            return
        if "FROM orgs" in sql and "SELECT id FROM" not in sql:
            self._rows = [{"plan_status": "free", "seats_paid": 0, "paid_until": None}]
            return
        if "FROM members" in sql:
            self._rows = [{"role": "owner", "c": 1}, {"role": "advisor", "c": 2}]
            return
        if "SUM(" in sql:
            # 真实 MySQL 的聚合查询恒返回一行 (无匹配时为 NULL), 不能返回空集。
            # 列名取 SQL 里的 `AS <alias>`, 让调用方按名取值。
            alias = "agg"
            if " AS " in sql:
                alias = sql.split(" AS ", 1)[1].split()[0].rstrip(",")
            self._rows = [{alias: 0}]
            return
        self._rows = []

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


def _run_usage(existing_tables: set[str], monkeypatch) -> tuple[dict, FakeCursor]:
    """以指定表集合跑一遍 get_org_usage 的查询体."""
    cur = FakeCursor(existing_tables)
    monkeypatch.setattr(orgs_me, "db_cursor", lambda: _nullcontext(cur))
    monkeypatch.setattr(orgs_me, "_table_exists_cache", {}, raising=False)
    result = orgs_me.get_org_usage(user={"role": "owner", "org_id": "org_x"}, org_id="org_x")
    return result, cur


class _nullcontext:
    def __init__(self, cur):
        self.cur = cur

    def __enter__(self):
        return self.cur

    def __exit__(self, *exc):
        return False


_SAAS_TABLE_NAMES = ("saas_api_usage", "saas_key_orders", "saas_invoices")


class TestCommunityDegrade:
    """社区版: 三张 saas 表都不存在."""

    @pytest.mark.parametrize("table", _SAAS_TABLE_NAMES)
    def test_never_touches_saas_tables(self, table, monkeypatch):
        result, cur = _run_usage(set(), monkeypatch)
        # 只允许在探测阶段以字符串形式出现, 不得有 FROM/INTO saas_* 访问
        offenders = [s for s in cur.executed
                     if table in s and "information_schema" not in s]
        assert not offenders, f"社区版仍访问了 {table}: {offenders}"

    def test_reports_billing_unavailable(self, monkeypatch):
        result, _ = _run_usage(set(), monkeypatch)
        assert result["billing_available"] is False
        assert result["invoices"] == []
        assert result["key_orders"] == []
        # 套餐与成员统计仍应可用 (这些表在 shared 的 schema.sql 里)
        assert result["plan"]["status"] == "free"
        assert result["members"]["owner"] == 1
        assert result["members"]["advisor"] == 2

    def test_response_shape_stable(self, monkeypatch):
        """降级时字段必须齐全 —— 前端不能因为缺 key 而崩."""
        result, _ = _run_usage(set(), monkeypatch)
        for key in ("billing_available", "plan", "members",
                    "api_calls", "invoices", "key_orders"):
            assert key in result, f"社区版响应缺字段 {key}"
        for key in ("total", "this_month", "this_year", "purchased",
                    "annual_quota", "monthly_quota"):
            assert key in result["api_calls"], f"api_calls 缺字段 {key}"


class TestSaasFull:
    """SaaS 版: 三张表都在, 应走完整查询."""

    def test_billing_available_true(self, monkeypatch):
        result, _ = _run_usage(set(_SAAS_TABLE_NAMES), monkeypatch)
        assert result["billing_available"] is True

    def test_queries_key_orders_by_org_id(self, monkeypatch):
        """P2.2: 订单按 org_id 关联, org_name 仅作旧数据回落."""
        result, cur = _run_usage(set(_SAAS_TABLE_NAMES), monkeypatch)
        key_sql = [s for s in cur.executed if "saas_key_orders" in s
                   and "information_schema" not in s]
        assert key_sql, "SaaS 版应查询 saas_key_orders"
        assert any("org_id = %s" in s for s in key_sql), \
            "订单查询应优先按 org_id 关联, 而非 org_name"
        assert any("org_name" in s and "org_id IS NULL" in s for s in key_sql), \
            "org_name 关联应仅作为 org_id 为空时的回落"


class TestTableExistsCache:
    """探测结果按进程缓存, 避免每次请求都查 information_schema."""

    def test_cache_prevents_repeat_probe(self, monkeypatch):
        cur = FakeCursor(set(_SAAS_TABLE_NAMES))
        monkeypatch.setattr(orgs_me, "_table_exists_cache", {}, raising=False)
        assert orgs_me._table_exists(cur, "saas_api_usage") is True
        probes = [s for s in cur.executed if "information_schema" in s]
        assert len(probes) == 1
        # 第二次直接命中缓存, 不再查 information_schema
        assert orgs_me._table_exists(cur, "saas_api_usage") is True
        probes = [s for s in cur.executed if "information_schema" in s]
        assert len(probes) == 1, "第二次调用应命中缓存"

    def test_probe_failure_treated_as_absent(self, monkeypatch):
        """探测本身异常时不能打断请求 (保守当作不存在)."""

        class ExplodingCursor(FakeCursor):
            def execute(self, sql, params=None):
                if "information_schema" in sql:
                    raise RuntimeError("no permission")
                super().execute(sql, params)

        cur = ExplodingCursor(set())
        monkeypatch.setattr(orgs_me, "_table_exists_cache", {}, raising=False)
        assert orgs_me._table_exists(cur, "saas_api_usage") is False
