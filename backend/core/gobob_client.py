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


def search_schools(q: str = "", country: str = "", page: int = 1, page_size: int = 20) -> dict | None:
    ck = f"schools:{q}:{country}:{page}:{page_size}"
    return _get("/api/smb/v1/schools",
                params={"q": q, "country": country, "page": page, "page_size": page_size},
                cache_key=ck, cache_ttl=3600)


def get_school(school_id: str) -> dict | None:
    return _get(f"/api/smb/v1/schools/{school_id}", cache_key=f"school:{school_id}")


def match(student_input: dict) -> dict | None:
    """智能匹配 Top N。POST，不缓存。"""
    return _post("/api/smb/v1/match", student_input)


def match_single(payload: dict) -> dict | None:
    return _post("/api/smb/v1/match-single", payload)
