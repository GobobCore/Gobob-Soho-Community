"""
api/assessment.py — 智能评估桥

获客门户的评估请求 → 转发 Gobob Data API → 本地存快照（assessments）。
匿名可用；留资后 lead_id 关联快照，供顾问跟进时参考。
"""

from fastapi import APIRouter, Depends, HTTPException, Request
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
def match(req: MatchReq, request: Request, user: dict = Depends(auth.get_optional_user)):
    """智能匹配 Top N。匿名可用。成功则本地存快照。支持 ?org=slug 归属。"""
    _require_gobob()
    # 多机构 SaaS: ?org=slug 参数 (优先于匿名默认)
    org_slug = request.query_params.get("org")
    org_id_from_slug = _org_from_slug(org_slug) if org_slug else None
    if org_slug and not org_id_from_slug:
        raise HTTPException(status_code=404, detail=f"机构不存在或已停用: {org_slug}")
    result = gobob_client.match(req.form)
    if result is None:
        detail = "智能匹配服务暂时不可用"
        if getattr(gobob_client, "LAST_ERROR", None):
            detail = f"智能匹配服务暂时不可用 ({gobob_client.LAST_ERROR})"
        raise HTTPException(status_code=502, detail=detail)

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
                    user.get("org_id") or org_id_from_slug or _default_org(),
                    req.lead_id,
                    user.get("member_id"),
                    result.get("assessment_id") or result.get("_assessment_session_id"),
                    json.dumps(req.form, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
    except Exception:
        pass  # 快照失败不影响返回结果
    result["soho_assessment_id"] = sid
    return result
# ── 内部评估历史（需登录）────────────────────────────────────────

@router.get("/history")
def assessment_history(
    user: dict = Depends(auth.get_current_user),
    page: int = 1,
    page_size: int = 50,
):
    """列出当前用户（或机构）的评估历史."""
    from core.tenancy import get_org_id
    org_id = user.get("org_id")
    offset = (page - 1) * page_size
    with db_cursor() as cur:
        where = "WHERE a.org_id=%s"
        params = [org_id]
        # 学生/家长只看自己的, owner/advisor 看全机构
        if user.get("role") in ("student", "parent"):
            where += " AND a.member_id=%s"
            params.append(user.get("member_id"))
        cur.execute(f"SELECT COUNT(*) AS c FROM assessments a {where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT a.id, a.member_id, a.lead_id, a.gobob_assessment_id, a.form_json, a.result_json, a.created_at,
                               m.name AS member_name, m.role AS member_role,
                               l.student_name AS lead_name, l.student_phone AS lead_phone, l.student_wechat AS lead_wechat
                FROM assessments a
                LEFT JOIN members m ON m.id = a.member_id
                LEFT JOIN leads l ON l.lead_id = a.lead_id
                {where}  -- WHERE 已包含 a.org_id 等
                ORDER BY a.created_at DESC LIMIT %s OFFSET %s""",
            params + [page_size, offset],
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["created_at"] = str(d["created_at"]) if d.get("created_at") else None
            # 从 result_json 提取摘要
            res = d.get("result_json") or {}
            if isinstance(res, str):
                import json
                try: res = json.loads(res)
                except: res = {}
            d["match_count"] = len(res.get("matches", [])) if isinstance(res, dict) else 0
            d["top_school"] = (res.get("matches", [{}])[0].get("school_name_zh") or
                              res.get("matches", [{}])[0].get("school_name") or "") if isinstance(res, dict) else ""
            # 从 form_json 提取学生信息
            form = d.get("form_json") or {}
            if isinstance(form, str):
                try: form = json.loads(form)
                except: form = {}
            d["student_name"] = form.get("basic", {}).get("name", "") if isinstance(form, dict) else ""
            rows.append(d)
    return {"total": total, "items": rows}


@router.get("/{assessment_id}")
def assessment_detail(
    assessment_id: str,
    user: dict = Depends(auth.get_current_user),
):
    """评估详情."""
    with db_cursor() as cur:
        cur.execute(
            "SELECT a.*, m.name AS member_name, l.student_name AS lead_name, l.student_phone AS lead_phone FROM assessments a "
            "LEFT JOIN members m ON m.id = a.member_id "
            "LEFT JOIN leads l ON l.lead_id = a.lead_id WHERE a.id=%s",
            (assessment_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="评估不存在")
        d = dict(row)
        d["created_at"] = str(d["created_at"]) if d.get("created_at") else None
        import json
        for f in ("form_json", "result_json"):
            v = d.get(f)
            if isinstance(v, str):
                try: d[f] = json.loads(v)
                except: pass
    # 权限检查: 仅本机构可看
    if d.get("org_id") != user.get("org_id"):
        raise HTTPException(status_code=403, detail="无权访问")
    return d



def _default_org() -> str | None:
    """匿名评估时归到默认机构（自托管单机构场景）。"""
    try:
        with db_cursor() as cur:
            cur.execute("SELECT id FROM orgs ORDER BY created_at LIMIT 1")
            row = cur.fetchone()
            return row["id"] if row else None
    except Exception:
        return None


def _org_from_slug(slug: str | None) -> str | None:
    """多机构 SaaS: 从 slug 解析 org_id (跟 capture ?org= 一致)."""
    if not slug:
        return None
    try:
        with db_cursor() as cur:
            cur.execute("SELECT id FROM orgs WHERE slug=%s AND disabled=0 LIMIT 1", (slug,))
            row = cur.fetchone()
            return row["id"] if row else None
    except Exception:
        return None


# ── 获客门户数据代理（匿名可用，转发 Gobob SMB，带缓存/降级）─────

@router.get("/schools/lookup")
def schools_lookup(q: str = "", limit: int = 20, edu_level: str | None = None):
    """院校名联想（表单 SchoolPicker 用）。edu_level=high_school 走 gobob SMB。"""
    if not gobob_client.is_enabled():
        return {"items": []}
    items = gobob_client.schools_lookup(q, limit, edu_level) or []
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
