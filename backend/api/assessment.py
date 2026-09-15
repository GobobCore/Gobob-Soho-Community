"""
api/assessment.py — 智能评估桥

获客门户的评估请求 → 转发 Gobob Data API → 本地存快照（assessments）。
匿名可用；留资后 lead_id 关联快照，供顾问跟进时参考。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import auth, gobob_client
from core.database import db_cursor
from core.id_gen import new_id

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


def _require_gobob():
    if not gobob_client.is_enabled():
        raise HTTPException(status_code=503, detail="智能评估未启用（未配置 Gobob API Key）")


@router.get("/meta")
def assessment_meta():
    """表单元数据（国家/学位/学科/国内校 tier），远程 + 缓存。匿名可用。"""
    _require_gobob()
    data = gobob_client.get_assessment_meta()
    if data is None:
        raise HTTPException(status_code=502, detail="评估数据服务暂时不可用")
    return data


class MatchReq(BaseModel):
    form: dict
    lead_id: str | None = None  # 留资后关联


@router.post("/match")
def match(req: MatchReq, user: dict = Depends(auth.get_optional_user)):
    """智能匹配 Top N。匿名可用。成功则本地存快照。"""
    _require_gobob()
    result = gobob_client.match(req.form)
    if result is None:
        raise HTTPException(status_code=502, detail="智能匹配服务暂时不可用")

    # 本地快照
    import json
    sid = new_id()
    try:
        with db_cursor() as cur:
            cur.execute(
                """INSERT INTO assessments
                   (id, org_id, lead_id, member_id, gobob_assessment_id, form_json, result_json)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    sid,
                    user.get("org_id") or _default_org(),
                    req.lead_id,
                    user.get("member_id"),
                    result.get("assessment_id"),
                    json.dumps(req.form, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
    except Exception:
        pass  # 快照失败不影响返回结果
    result["soho_assessment_id"] = sid
    return result


def _default_org() -> str | None:
    """匿名评估时归到默认机构（自托管单机构场景）。"""
    try:
        with db_cursor() as cur:
            cur.execute("SELECT id FROM orgs ORDER BY created_at LIMIT 1")
            row = cur.fetchone()
            return row["id"] if row else None
    except Exception:
        return None


# ── 获客门户数据代理（匿名可用，转发 Gobob SMB，带缓存/降级）─────

@router.get("/schools/lookup")
def schools_lookup(q: str = "", limit: int = 20):
    """院校名联想（表单 SchoolPicker 用）。"""
    if not gobob_client.is_enabled():
        return {"items": []}
    items = gobob_client.schools_lookup(q, limit) or []
    return {"items": items}


@router.get("/schools/{school_id}")
def school_detail(school_id: str):
    _require_gobob()
    data = gobob_client.get_school(school_id)
    if data is None:
        raise HTTPException(status_code=502, detail="院校数据暂时不可用")
    return data


@router.get("/majors")
def majors(limit: int = 200):
    if not gobob_client.is_enabled():
        return {"items": []}
    data = gobob_client.get_majors(limit)
    return data or {"items": []}


class AiAskReq(BaseModel):
    question: str
    student_profile: dict | None = None


@router.post("/ai-ask")
def ai_ask(req: AiAskReq):
    """评估页 AI 问答（转发 Gobob LLM）。无 Key 时 503。"""
    _require_gobob()
    result = gobob_client.llm_ask(req.model_dump())
    if result is None:
        raise HTTPException(status_code=502, detail="AI 服务暂时不可用")
    return result
