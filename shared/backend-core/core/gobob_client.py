"""
core/gobob_client.py — Gobob Data API 客户端

R-Refactor (2026-09-18 13:50): _map_to_gobob_match 与 phase3.MatchRequest 真实 schema 对齐
  (current_gpa / has_research / budget_per_year / degree 别名归一), _post 增加 LAST_ERROR 透出.
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
    # X-Soho-Org-Id: Gobob 落 api_key_logs.org_id, 用于 SaaS 运营后台按机构聚合用量
    h = {"X-API-Key": settings.gobob_api_key}
    if settings.gobob_org_id:
        h["X-Soho-Org-Id"] = settings.gobob_org_id
    return h


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
    """POST 远程 API（匹配 / 评估，不缓存）。失败原因存 LAST_ERROR 供上层透出。"""
    global LAST_ERROR
    if not is_enabled():
        LAST_ERROR = "未配置 GOBOB_API_KEY"
        return None
    url = f"{settings.gobob_api_base.rstrip('/')}{path}"
    try:
        resp = httpx.post(url, headers=_headers(), json=body, timeout=_TIMEOUT)
        if resp.status_code == 200:
            LAST_ERROR = None
            return resp.json()
        LAST_ERROR = f"HTTP {resp.status_code}: {resp.text[:300]}"
        log.warning("gobob POST %s -> %s %s", path, resp.status_code, resp.text[:200])
    except Exception as e:
        LAST_ERROR = f"{type(e).__name__}: {e}"
        log.warning("gobob POST %s error: %s", path, e)
    return None


LAST_ERROR: str | None = None


# ── 业务封装 ──────────────────────────────────────────────────────

def get_assessment_meta() -> dict | None:
    """评估表单元数据（国家/学位/学科/国内校 tier）。缓存 24h。"""
    return _get("/api/smb/v1/meta", cache_key="assessment_meta")


def schools_lookup(q: str = "", limit: int = 20, edu_level: str | None = None) -> list | None:
    """院校名联想（SchoolPicker 用）。返回轻量列表。"""
    params = {"q": q, "page_size": limit}
    if edu_level:
        params["edu_level"] = edu_level
    data = _get("/api/smb/v1/schools", params=params,
                cache_key=f"slookup:{q}:{limit}:{edu_level or 'all'}", cache_ttl=3600)
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


# 当前 gobob phase3.MatchRequest 真实 schema (2026-09-18 核对):
#   current_stage: Literal[...9 个学段码] | None
#   current_gpa: float (ge=0, le=5.0)          ← 注意叫 current_gpa, 不是 gpa!
#   current_school_tier: Literal["C9","985","211","双非","海外","其他"] | None
#   toefl int 0-120 / ielts float 0-9 / gre_total 200-340 / gmat_total 200-800
#   english_sub_reading/listening/speaking/writing: float | None
#   target_countries: list[str] / target_degree: Literal / target_major / current_major
#   has_research: bool / has_internship: bool   ← 不是 research_exp int!
#   publications int 0-50 / work_years int 0-20 / contact_status str
#   budget_per_year: int (USD)                  ← 不是 budget_min/max!
#   living_min/living_max: int (万/年) / funding_source / campus_preference / school_size
#   accept_pathway / extracurricular / international_exchange(_top) / portfolio / scholarship_needed
# 不存在的字段 (会被 pydantic 忽略, 不再透传): target_intake / current_school_id /
#   current_stage_year / gpa / research_exp / internship_exp / budget_min / budget_max

_TIER_VALID = {"C9", "985", "211", "双非", "海外", "其他"}


def _map_to_gobob_match(f: dict) -> dict:
    """前端 form → gobob phase3.MatchRequest 字段名映射 (与真实 schema 对齐)."""
    m: dict = {}
    # 1) 学段: MatchRequest.current_stage (Literal, 我们的 9 个学段码全兼容)
    stage = f.get("current_stage") or f.get("current_edu_level")
    if stage:
        m["current_stage"] = stage
        m["current_edu_level"] = stage  # 自由字符串, 兜底旧 matcher
    # 2) GPA → current_gpa (0-5.0), 按 gpa_scale 归一到 4.0 制
    if f.get("gpa"):
        gpa = float(f["gpa"])
        scale = str(f.get("gpa_scale", "4.0"))
        if scale == "100":
            gpa = gpa / 25.0
        elif scale == "5.0":
            gpa = gpa / 5.0 * 4.0
        elif scale == "4.3":
            gpa = gpa / 4.3 * 4.0
        gpa = max(0.0, min(5.0, round(gpa, 2)))
        if gpa > 0:
            m["current_gpa"] = gpa
    # 3) 学校背景: 只透传合法 Literal 值
    tier = f.get("current_school_tier")
    if isinstance(tier, str) and tier in _TIER_VALID:
        m["current_school_tier"] = tier
    elif tier in (1, 2, 3, 4):
        m["current_school_tier"] = {1: "985", 2: "211", 3: "双非", 4: "海外"}[int(tier)]
    # 4) 目标 (degree 有 Literal 约束, 先把前端括号后缀归一)
    if f.get("target_countries"):
        m["target_countries"] = f["target_countries"]
    if f.get("target_degree"):
        deg_alias = {
            "Bachelor (transfer)": "Bachelor",
            "Master (second)": "Master",
            "PhD (visiting)": "PhD",
        }
        m["target_degree"] = deg_alias.get(f["target_degree"], f["target_degree"])
    if f.get("target_major"):
        m["target_major"] = f["target_major"]
    if f.get("current_major"):
        m["current_major"] = f["current_major"]
    # 5) 英语: 只认 toefl(0-120)/ielts(0-9), 其他体系不传
    test = (f.get("english_test") or "").upper()
    score = f.get("english_score") or 0
    if score:
        try:
            s = float(score)
            if test == "IELTS" and 0 < s <= 9.0:
                m["ielts"] = s
            elif test == "TOEFL" and 0 < s <= 120:
                m["toefl"] = int(s)
            # PTE/Duolingo: MatchRequest 无对应字段, 不传
        except (TypeError, ValueError):
            pass
    # 小分
    for k in ("english_sub_reading", "english_sub_listening",
              "english_sub_speaking", "english_sub_writing"):
        v = f.get(k)
        if v:
            try:
                m[k] = float(v)
            except (TypeError, ValueError):
                pass
    # 6) 标化: 前端可能发 standardized_tests dict 或平铺字段
    std = f.get("standardized_tests") or {}
    gre = f.get("gre_total") or std.get("GRE")
    gmat = f.get("gmat_total") or std.get("GMAT")
    if gre and 200 <= int(gre) <= 340:
        m["gre_total"] = int(gre)
    if gmat and 200 <= int(gmat) <= 800:
        m["gmat_total"] = int(gmat)
    # 7) 软背景: research_exp(int) → has_research(bool); 列表→计数
    m["has_research"] = bool(f.get("research_exp"))
    m["has_internship"] = bool(f.get("internship_exp"))
    comp = list(f.get("competition") or []) + list(f.get("other_competition") or [])
    if comp:
        m["competition_count"] = min(20, len(comp))
    if f.get("volunteer"):
        m["volunteer_count"] = min(20, len(f["volunteer"]))
    if f.get("publications") is not None:
        m["publications"] = max(0, min(50, int(f["publications"])))
    if f.get("work_years") is not None:
        m["work_years"] = max(0, min(20, int(f["work_years"])))
    # 8) 预算: 万RMB → USD (budget_per_year), 生活费原样 (万)
    try:
        bm = float(f.get("budget_max") or f.get("budget_min") or 0)
        if bm > 0:
            m["budget_per_year"] = int(bm * 10000 / 7.2)
    except (TypeError, ValueError):
        pass
    for k in ("living_min", "living_max"):
        v = f.get(k)
        if v is not None and int(v or 0) >= 0:
            m[k] = int(v)
    # 9) 其余直传字段 (MatchRequest 都认识)
    for k in ("funding_source", "contact_status", "accept_pathway",
              "extracurricular", "international_exchange", "international_exchange_top",
              "campus_preference", "school_size", "portfolio", "scholarship_needed"):
        if f.get(k) is not None:
            m[k] = f[k]
    # campus/school_size 有 Literal 约束, 非法值丢弃
    if m.get("campus_preference") not in ("urban", "suburban", "rural", None):
        m.pop("campus_preference", None)
    if m.get("school_size") not in ("large", "medium", "small", None):
        m.pop("school_size", None)
    return m


def match_single(payload: dict) -> dict | None:
    return _post("/api/smb/v1/match-single", payload)


def llm_ask(payload: dict) -> dict | None:
    """评估页 AI 问答。SMB 侧若无此端点则返回 None（前端降级隐藏）。"""
    return _post("/api/smb/v1/llm-ask", payload)
