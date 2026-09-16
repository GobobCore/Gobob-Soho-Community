"""
gobob_data_api_mock.py — Gobob Data API 仿真 fixture
====================================================

社区版跑测试不需要真 Gobob Data API Key, 用这个 mock 提供假响应.

用法 (conftest.py 或具体测试):
    from tests.gobob_data_api_mock import mock_gobob_data_api

    def test_assessment_form_loads(monkeypatch):
        mock_gobob_data_api(monkeypatch, base_url="http://mock-gobob")
        # 现在 assessment 端点会从 mock http://mock-gobob 拿假数据

数据结构 (跟真 Gobob API 一致, 详见 backend/api/smb_v1.py):
    - /api/smb/v1/meta: {countries, stages, disciplines, cn_school_levels}
    - /api/smb/v1/schools: {total, page, items}
    - /api/smb/v1/match: {ok, matches, by_country, tier_groups, ...}
"""

import json
from typing import Any


# ── Mock 数据 ──

MOCK_COUNTRIES = [
    {
        "country_id": "US", "iso_code": "US", "country_name": "美国",
        "flag_emoji": "🇺🇸", "primary_language": "English",
        "english_required": 1, "accepted_english_tests": "TOEFL/IELTS/PTE",
        "local_language_test": None, "local_test_required": 0,
        "standardized_tests": "GRE/GMAT",
    },
    {
        "country_id": "UK", "iso_code": "GB", "country_name": "英国",
        "flag_emoji": "🇬🇧", "primary_language": "English",
        "english_required": 1, "accepted_english_tests": "IELTS/TOEFL",
        "local_language_test": None, "local_test_required": 0,
        "standardized_tests": None,
    },
    {
        "country_id": "JP", "iso_code": "JP", "country_name": "日本",
        "flag_emoji": "🇯🇵", "primary_language": "Japanese",
        "english_required": 0, "accepted_english_tests": "TOEFL/IELTS (SGU 项目)",
        "local_language_test": "JLPT N1/N2", "local_test_required": 1,
        "standardized_tests": "GRE (SGU)",
    },
]

MOCK_STAGES = [
    {"current_stage": "high_school", "eligible_degree": "Bachelor", "min_years_to_completion": 4,
     "notes": "直申本科"},
    {"current_stage": "undergraduate", "eligible_degree": "Master", "min_years_to_completion": 2,
     "notes": "应届本科可申硕"},
    {"current_stage": "graduate_master", "eligible_degree": "PhD", "min_years_to_completion": 4,
     "notes": "硕申博"},
]

MOCK_DISCIPLINES = [
    {"code": "cs", "name_zh": "计算机科学", "name_en": "Computer Science", "parent_code": "eng", "level": 2},
    {"code": "biz.mba", "name_zh": "工商管理硕士", "name_en": "MBA & Strategy", "parent_code": "biz", "level": 2},
    {"code": "math", "name_zh": "数学", "name_en": "Mathematics", "parent_code": "sci", "level": 2},
]

MOCK_CN_SCHOOL_LEVELS = [
    {"code": "985", "name_cn": "985 大学", "name_en": "985 University", "weight": 100},
    {"code": "211", "name_cn": "211 大学", "name_en": "211 University", "weight": 80},
    {"code": "double_first_class", "name_cn": "双一流", "name_en": "Double First-Class", "weight": 95},
]

MOCK_SCHOOLS = [
    {
        "school_id": "sch_mit", "name_en": "Massachusetts Institute of Technology",
        "name_cn": "麻省理工学院", "country": "United States", "country_code": "US",
        "city_name": "Cambridge", "ranking_qs": 1, "ranking_the": 2, "ranking_usnews": 2,
        "school_type": "private", "tuition_intl": 55000, "living_cost": 15000,
        "currency": "USD", "website": "https://www.mit.edu",
        "logo_url": None, "logo_local": None,
    },
    {
        "school_id": "sch_oxford", "name_en": "University of Oxford",
        "name_cn": "牛津大学", "country": "United Kingdom", "country_code": "UK",
        "city_name": "Oxford", "ranking_qs": 3, "ranking_the": 1, "ranking_usnews": 5,
        "school_type": "public", "tuition_intl": 35000, "living_cost": 12000,
        "currency": "GBP", "website": "https://www.ox.ac.uk",
        "logo_url": None, "logo_local": None,
    },
    {
        "school_id": "sch_tokyo", "name_en": "University of Tokyo",
        "name_cn": "东京大学", "country": "Japan", "country_code": "JP",
        "city_name": "Tokyo", "ranking_qs": 28, "ranking_the": 39, "ranking_usnews": 81,
        "school_type": "public", "tuition_intl": 5000, "living_cost": 8000,
        "currency": "JPY", "website": "https://www.u-tokyo.ac.jp",
        "logo_url": None, "logo_local": None,
    },
]


def _make_match_response(req: dict) -> dict:
    """根据评估输入生成 3-6 个 mock 匹配结果."""
    target = req.get("target_countries", ["US"])
    target = target[0] if target else "US"
    gpa = float(req.get("gpa", 3.5))
    toefl = int(req.get("toefl", 100))

    # 按 gpa + 国家简单匹配
    matches = []
    for school in MOCK_SCHOOLS:
        if school["country_code"] != target:
            continue
        # 简单评分: GPA 高=match, 低=reach
        if gpa >= 3.7:
            tier = "match"
            prob = 0.78
        elif gpa >= 3.3:
            tier = "reach"
            prob = 0.45
        else:
            tier = "safety"
            prob = 0.85
        matches.append({
            "school_id": school["school_id"],
            "school_name_en": school["name_en"],
            "school_name_cn": school["name_cn"],
            "country": school["country"],
            "tier": tier,
            "admission_probability": prob,
            "ranking_qs": school["ranking_qs"],
        })

    return {
        "ok": True,
        "note": "mock 响应 (测试用)",
        "algorithm": {"model": "mock_v1", "weights": {}},
        "request": req,
        "matches": matches,
        "by_country": {target: matches},
        "countries_analyzed": [target],
        "total": len(matches),
        "user_profile": {},
        "country_strategy": {},
        "tier_groups": {
            "reach": [m for m in matches if m["tier"] == "reach"],
            "match": [m for m in matches if m["tier"] == "match"],
            "safety": [m for m in matches if m["tier"] == "safety"],
        },
        "tier_summary": {
            "reach_count": len([m for m in matches if m["tier"] == "reach"]),
            "match_count": len([m for m in matches if m["tier"] == "match"]),
            "safety_count": len([m for m in matches if m["tier"] == "safety"]),
        },
        "matches_by_tier": {},
        "_assessment_session_id": "mock_session_001",
        "_user_id": "mock_user_001",
    }


# ── 替换 gobob_client 的请求实现 ──

def install_gobob_mock(monkeypatch, base_url: str = "http://mock-gobob") -> None:
    """替换 core/gobob_client.py 的请求, 用本地 mock 数据.

    用法:
        def test_x(monkeypatch):
            install_gobob_mock(monkeypatch)
            # 评估调用会拿 mock 数据
    """
    from core import gobob_client
    from core.config import get_settings

    # 改 settings, 让 gobob_client 觉得 base_url 指向 mock
    settings = get_settings()
    monkeypatch.setattr(settings, "gobob_api_base", base_url)
    monkeypatch.setattr(gobob_client.settings, "gobob_api_base", base_url)
    # 关键: 强制 is_enabled() 返 True, 不然 assessment._require_gobob() 会 503
    monkeypatch.setattr(gobob_client, "is_enabled", lambda: True)
    # gobob_api_key 也设一下 (从 settings 读)
    monkeypatch.setattr(settings, "gobob_api_key", "mock-key")
    monkeypatch.setattr(gobob_client.settings, "gobob_api_key", "mock-key")
    # 绕开 gobob_api_cache 表 (测试不连 DB, 强制 cache miss)
    monkeypatch.setattr(gobob_client, "_cache_get", lambda *args, **kwargs: None)
    monkeypatch.setattr(gobob_client, "_cache_set", lambda *args, **kwargs: None)

    # 替换 httpx 调用 — gobob_client 直接用 `httpx.get` / `httpx.post` (httpx 模块函数)
    # 所以 monkeypatch 实际是 patch httpx 模块的 get/post 属性
    import httpx
    def fake_get(url, headers=None, params=None, timeout=None, **kwargs):
        path = str(url)
        if "/meta" in path:
            return _MockResponse(200, {
                "countries": MOCK_COUNTRIES,
                "stages": MOCK_STAGES,
                "disciplines": MOCK_DISCIPLINES,
                "cn_school_levels": MOCK_CN_SCHOOL_LEVELS,
            })
        if "/schools" in path:
            q = (params or {}).get("q", "").lower() if params else ""
            items = [s for s in MOCK_SCHOOLS if q in s["name_en"].lower() or q in s["name_cn"]]
            return _MockResponse(200, {
                "total": len(items),
                "page": 1,
                "page_size": 20,
                "items": items or MOCK_SCHOOLS,
            })
        return _MockResponse(404, {"detail": "not found"})

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        path = str(url)
        if "/match" in path:
            return _MockResponse(200, _make_match_response(json or {}))
        return _MockResponse(404, {"detail": "not found"})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)


class _MockResponse:
    """Mock httpx.Response."""
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json = json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(
                f"{self.status_code} error",
                request=None,
                response=None,
            )

    def json(self) -> dict:
        return self._json


# ── 便捷函数: 社区版测试直接用 ──

def mock_gobob_data_api(monkeypatch, base_url: str = "http://mock-gobob") -> None:
    """install_gobob_mock 的别名, 调用更直观."""
    install_gobob_mock(monkeypatch, base_url)
