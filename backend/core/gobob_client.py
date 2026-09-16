"""
core/gobob_client.py — Gobob Data API 客户端

SOHO 不存院校 / 专业 / 排名等数据，全部远程调 Gobob SMB API（/api/smb/v1/*）。
- X-API-Key 授权（env GOBOB_API_KEY）
- 本地缓存（gobob_api_cache 表）减少远程调用
- 熔断 / 降级：远程不可用时返回缓存（哪怕过期）或空，不让核心业务崩

无 Key 时 is_enabled() = False，智能评估 / 院校功能优雅关闭。
"""

import json
import logging
from datetime import datetime, timedelta

import httpx

from .config import get_settings
from .database import db_cursor

log = logging.getLogger("gobob_client")
settings = get_settings()

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def is_enabled() -> bool:
    return bool(settings.gobob_api_key)


def _headers() -> dict:
    return {"X-API-Key": settings.gobob_api_key}


# ── 缓存 ─────────────────────────────────────────────────────────

def _cache_get(key: str) -> dict | None:
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT payload, expires_at FROM gobob_api_cache WHERE cache_key=%s LIMIT 1",
                (key,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {"payload": json.loads(row["payload"]), "fresh": row["expires_at"] > datetime.utcnow()}
    except Exception as e:  # 缓存表不存在等 → 视为未命中
        log.warning("cache_get error: %s", e)
        return None


def _cache_set(key: str, payload: dict, ttl: int | None = None) -> None:
    ttl = ttl if ttl is not None else settings.gobob_cache_ttl
    expires = datetime.utcnow() + timedelta(seconds=ttl)
    try:
        with db_cursor() as cur:
            cur.execute(
                """INSERT INTO gobob_api_cache (cache_key, payload, expires_at)
                   VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE payload=VALUES(payload), expires_at=VALUES(expires_at)""",
                (key, json.dumps(payload, ensure_ascii=False), expires),
            )
    except Exception as e:
        log.warning("cache_set error: %s", e)


# ── 远程调用 ──────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None, cache_key: str | None = None,
         cache_ttl: int | None = None) -> dict | None:
    """GET 远程 API。成功写缓存；失败降级到缓存（含过期缓存）。"""
    if cache_key:
        hit = _cache_get(cache_key)
        if hit and hit["fresh"]:
            return hit["payload"]
    if not is_enabled():
        # 无 Key：有过期缓存也返回（降级），否则 None
        if cache_key:
            hit = _cache_get(cache_key)
            if hit:
                return hit["payload"]
        return None
    url = f"{settings.gobob_api_base.rstrip('/')}{path}"
    try:
        resp = httpx.get(url, headers=_headers(), params=params or {}, timeout=_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            if cache_key:
                _cache_set(cache_key, data, cache_ttl)
            return data
        log.warning("gobob GET %s -> %s %s", path, resp.status_code, resp.text[:200])
    except Exception as e:
        log.warning("gobob GET %s error: %s", path, e)
    # 降级：过期缓存兜底
    if cache_key:
        hit = _cache_get(cache_key)
        if hit:
            return hit["payload"]
    return None


def _post(path: str, body: dict) -> dict | None:
    """POST 远程 API（匹配 / 评估，不缓存）。"""
    if not is_enabled():
        return None
    url = f"{settings.gobob_api_base.rstrip('/')}{path}"
    try:
        resp = httpx.post(url, headers=_headers(), json=body, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        log.warning("gobob POST %s -> %s %s", path, resp.status_code, resp.text[:200])
    except Exception as e:
        log.warning("gobob POST %s error: %s", path, e)
    return None


# ── 业务封装 ──────────────────────────────────────────────────────

def get_assessment_meta() -> dict | None:
    """评估表单元数据（国家/学位/学科/国内校 tier）。缓存 24h。"""
    return _get("/api/smb/v1/meta", cache_key="assessment_meta")


def schools_lookup(q: str = "", limit: int = 20) -> list | None:
    """院校名联想（SchoolPicker 用）。返回轻量列表。"""
    data = _get("/api/smb/v1/schools", params={"q": q, "page_size": limit},
                cache_key=f"slookup:{q}:{limit}", cache_ttl=3600)
    return data.get("items") if data else None


def get_majors(limit: int = 200) -> list | None:
    """专业列表（MajorPicker）。SMB 暂无 /majors，从 programs 去重，或远程补。"""
    return _get("/api/smb/v1/majors", params={"limit": limit}, cache_key=f"majors:{limit}")


def get_school(school_id: str) -> dict | None:
    return _get(f"/api/smb/v1/schools/{school_id}", cache_key=f"school:{school_id}")


def match(student_input: dict) -> dict | None:
    """智能匹配 Top N。POST，不缓存。

    R-Fix (2026-09-16): 前端 form 字段名 (current_stage/school_id/gpa/english_score) →
    Gobob match 期望字段名 (current_edu_level/toefl/gre_total) 的映射.
    """
    mapped = _map_to_gobob_match(student_input)
    return _post("/api/smb/v1/match", mapped)


def _map_to_gobob_match(f: dict) -> dict:
    """前端 form → Gobob match body 字段名 + 白名单映射。

    前端 form 含 30+ 字段, Gobob match 期望严格 schema (RejectExtras),
    多余字段直接报 ValidationError. 这里只挑 Gobob 认识的字段.
    """
    m = {}
    # 1) current_edu_level (前端 current_stage 字符串)
    if "current_stage" in f and "current_edu_level" not in f:
        m["current_edu_level"] = f["current_stage"]
    elif "current_edu_level" in f:
        m["current_edu_level"] = f["current_edu_level"]
    # 2) target_countries (ISO 代码数组, 前端已是 ISO 数组)
    if "target_countries" in f and f["target_countries"]:
        m["target_countries"] = f["target_countries"]
    # 3) target_degree (字符串)
    if "target_degree" in f and f["target_degree"]:
        m["target_degree"] = f["target_degree"]
    # 4) target_intake (e.g. "2027 Fall")
    if "target_intake" in f and f["target_intake"]:
        m["target_intake"] = f["target_intake"]
    # 5) target_major (英文名)
    if "target_major" in f and f["target_major"]:
        m["target_major"] = f["target_major"]
    # 6) current_school_id
    if "current_school_id" in f and f["current_school_id"]:
        m["current_school_id"] = f["current_school_id"]
    # 7) current_school_tier 1=985/2=211/3=双非/4=海外 → Gobob 字符串
    tier_map = {1: "985", 2: "211", 3: "double_first_class_b", 4: "overseas"}
    if "current_school_tier" in f and f["current_school_tier"] in tier_map:
        m["current_school_tier"] = tier_map[f["current_school_tier"]]
    # 8) gpa + gpa_scale (若 scale=100, 换算成 4.0)
    if "gpa" in f and f["gpa"]:
        gpa = float(f["gpa"])
        scale = f.get("gpa_scale", "4.0")
        if scale == "100":
            gpa = round(gpa / 25, 2)  # 100/25 ≈ 4.0
        elif scale == "5.0":
            gpa = round(gpa / 5 * 4, 2)
        elif scale == "4.3":
            gpa = round(gpa / 4.3 * 4, 2)
        m["gpa"] = gpa
    # 9) 英语分数 → toefl/ielts/pte/duolingo (Gobob 期望字段)
    test = f.get("english_test", "")
    score = f.get("english_score")
    if score and test:
        key = {"TOEFL": "toefl", "IELTS": "ielts", "PTE": "pte", "Duolingo": "duolingo"}.get(test.upper(), "toefl")
        m[key] = score
    # 10) GRE/GMAT 分数
    if "gre_total" in f and f["gre_total"]:
        m["gre_total"] = f["gre_total"]
    if "gmat_total" in f and f["gmat_total"]:
        m["gmat_total"] = f["gmat_total"]
    # 11) 软背景 (research/internship/工作年限)
    for k in ("research_exp", "internship_exp", "work_years"):
        if k in f and f[k] is not None:
            m[k] = f[k]
    # 12) 预算 (Gobob 期望 RMB, 前端单位是 万)
    if "budget_min" in f and f["budget_min"]:
        m["budget_min"] = int(f["budget_min"]) * 10000
        m["budget_max"] = int(f.get("budget_max", f["budget_min"])) * 10000
    # 13) 跨专业申请 (Gobob boolean)
    if "cross_disciplinary" in f:
        m["cross_disciplinary"] = f["cross_disciplinary"]
    # 14) 留学身份
    if "current_stage_year" in f:
        m["current_stage_year"] = f["current_stage_year"]
    return m


def match_single(payload: dict) -> dict | None:
    return _post("/api/smb/v1/match-single", payload)


def llm_ask(payload: dict) -> dict | None:
    """评估页 AI 问答。SMB 侧若无此端点则返回 None（前端降级隐藏）。"""
    return _post("/api/smb/v1/llm-ask", payload)
