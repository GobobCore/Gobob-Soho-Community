"""
api/leads.py — 线索池（CRM 生源管理）— Phase 5 升级

线索 → 跟进 → 转化 → 签约。看板 + 漏斗 + 分配 + 撞单 + 公海 + 流失分析。
"""

import json
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id, new_short_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/leads", tags=["leads"])

LEAD_STATUSES = {"new", "contacted", "qualified", "proposal", "negotiation", "converted", "lost", "recycled"}
LOST_REASONS = {"price_too_high", "chose_competitor", "decided_not_to_apply", "lost_contact", "other"}


def _can_see_all(user: dict) -> bool:
    return user.get("role") == auth.ROLE_OWNER


def _row_to_dict(row) -> dict:
    d = dict(row)
    for k in ("target_countries", "target_degrees", "target_majors", "tags", "team_members"):
        if d.get(k) and isinstance(d[k], str):
            try: d[k] = json.loads(d[k])
            except: pass
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _name_similarity(a: str, b: str) -> float:
    if not a or not b: return 0.0
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def _find_duplicates(org_id: str, *, student_phone=None, student_wechat=None,
                     student_name=None, parent_phone=None, exclude_lead_id=None) -> list:
    """匹配：手机精确 OR 微信精确 OR (姓名相似度≥0.85 AND 家长手机后 7 位一致)"""
    sql = "SELECT * FROM leads WHERE org_id=%s AND is_recycled=0"
    params = [org_id]
    if exclude_lead_id:
        sql += " AND lead_id != %s"
        params.append(exclude_lead_id)
    candidates = []
    with db_cursor() as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            hit = None
            if student_phone and row.get("student_phone") and row["student_phone"] == student_phone:
                hit = ("手机精确", 1.0)
            elif student_wechat and row.get("student_wechat") and row["student_wechat"] == student_wechat:
                hit = ("微信精确", 1.0)
            elif (student_name and row.get("student_name") and
                  _name_similarity(student_name, row["student_name"]) >= 0.85 and
                  parent_phone and row.get("parent_phone") and
                  parent_phone[-7:] == row["parent_phone"][-7:]):
                hit = ("姓名+家长手机", 0.9)
            if hit:
                candidates.append({**_row_to_dict(row), "_match_reason": hit[0], "_match_score": hit[1]})
    return candidates


def _org_setting(conn, org_id: str, key: str, default):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT settings FROM orgs WHERE id=%s", (org_id,))
            row = cur.fetchone()
        if row and row.get("settings"):
            try:
                s = json.loads(row["settings"]) if isinstance(row["settings"], str) else row["settings"]
                return s.get(key, default)
            except: pass
    except: pass
    return default


# ── 录入（带查重） ───────────────────────────────────────────────

class LeadCreate(BaseModel):
    student_name: str = Field(..., min_length=1)
    student_phone: str | None = None
    student_wechat: str | None = None
    student_email: str | None = None
    student_grade: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    parent_wechat: str | None = None
    current_school: str | None = None
    gpa: float | None = None
    gpa_scale: str | None = None
    major: str | None = None
    language_test: str | None = None
    current_score: float | None = None
    target_score: float | None = None
    target_countries: list | None = None
    target_degrees: list | None = None
    target_majors: list | None = None
    target_year: int | None = None
    budget_range: str | None = None
    source: str | None = None
    source_detail: str | None = None
    priority: int = 3
    assigned_advisor_id: str | None = None
    notes: str | None = None
    assessment_id: str | None = None


@router.post("")
def create_lead(req: LeadCreate, user: dict = Depends(auth.require_staff),
                org_id: str = Depends(get_org_id)):
    advisor = req.assigned_advisor_id or user.get("member_id")
    # 查重
    duplicates = _find_duplicates(org_id,
                                   student_phone=req.student_phone,
                                   student_wechat=req.student_wechat,
                                   student_name=req.student_name,
                                   parent_phone=req.parent_phone)
    lead_id = new_short_id("lead_")
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO leads
               (lead_id, org_id, student_name, student_phone, student_wechat, student_email,
                student_grade, parent_name, parent_phone, parent_wechat,
                current_school, gpa, gpa_scale, major, language_test, current_score, target_score,
                target_countries, target_degrees, target_majors, target_year, budget_range,
                source, source_detail, status, priority, assigned_advisor_id, notes, assessment_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'new',%s,%s,%s,%s)""",
            (lead_id, org_id, req.student_name, req.student_phone, req.student_wechat, req.student_email,
             req.student_grade, req.parent_name, req.parent_phone, req.parent_wechat,
             req.current_school, req.gpa, req.gpa_scale, req.major, req.language_test,
             req.current_score, req.target_score,
             json.dumps(req.target_countries) if req.target_countries else None,
             json.dumps(req.target_degrees) if req.target_degrees else None,
             json.dumps(req.target_majors) if req.target_majors else None,
             req.target_year, req.budget_range, req.source, req.source_detail,
             req.priority, advisor, req.notes, req.assessment_id),
        )
    return {"lead_id": lead_id, "status": "new", "duplicates": duplicates}


# 获客门户匿名留资
@router.post("/capture")
def capture_lead(req: LeadCreate):
    lead_id = new_short_id("lead_")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM orgs ORDER BY created_at LIMIT 1")
        org = cur.fetchone()
        if not org:
            raise HTTPException(503, "系统未初始化")
        org_id = org["id"]
        duplicates = _find_duplicates(org_id,
                                       student_phone=req.student_phone,
                                       student_wechat=req.student_wechat,
                                       student_name=req.student_name,
                                       parent_phone=req.parent_phone)
        cur.execute(
            """INSERT INTO leads
               (lead_id, org_id, student_name, student_phone, student_wechat, student_email,
                target_countries, target_degrees, target_majors, source, source_detail, status,
                assessment_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'assessment',%s,'new',%s)""",
            (lead_id, org_id, req.student_name, req.student_phone, req.student_wechat,
             req.student_email,
             json.dumps(req.target_countries) if req.target_countries else None,
             json.dumps(req.target_degrees) if req.target_degrees else None,
             json.dumps(req.target_majors) if req.target_majors else None,
             req.source_detail, req.assessment_id),
        )
    return {"lead_id": lead_id, "ok": True, "duplicates": duplicates}


# ── 列表 / 看板 ─────────────────────────────────────────────────

@router.get("")
def list_leads(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id),
               status: str | None = None, q: str | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    where = ["l.org_id=%s", "l.is_recycled=0"]
    params = [org_id]
    if not _can_see_all(user):
        where.append("l.assigned_advisor_id=%s")
        params.append(user.get("member_id"))
    if status:
        where.append("l.status=%s")
        params.append(status)
    if q:
        where.append("(l.student_name LIKE %s OR l.student_phone LIKE %s OR l.student_wechat LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])
    sql_where = " AND ".join(where)
    offset = (page - 1) * page_size
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM leads l WHERE {sql_where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT l.*, m.name AS advisor_name
                FROM leads l LEFT JOIN members m ON m.id = l.assigned_advisor_id
                WHERE {sql_where}
                ORDER BY l.priority DESC, l.updated_at DESC LIMIT %s OFFSET %s""",
            params + [page_size, offset])
        rows = [_row_to_dict(r) for r in cur.fetchall()]
    return {"total": total, "page": page, "items": rows}


@router.get("/board")
def pipeline_board(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    """看板：按 pipeline 阶段分组（status 键关联）。含公海列（recycled）。"""
    where = "l.org_id=%s AND l.is_recycled=0"
    params = [org_id]
    if not _can_see_all(user):
        where += " AND l.assigned_advisor_id=%s"
        params.append(user.get("member_id"))
    with db_cursor() as cur:
        cur.execute("SELECT stage_id, name, sort_order FROM lead_pipeline_stages WHERE org_id=%s ORDER BY sort_order", (org_id,))
        stages = cur.fetchall()
        cur.execute(
            f"""SELECT l.lead_id, l.student_name, l.status, l.priority, l.source,
                       l.next_contact_at, l.assigned_advisor_id, m.name AS advisor_name
                FROM leads l LEFT JOIN members m ON m.id=l.assigned_advisor_id
                WHERE {where} ORDER BY l.priority DESC, l.updated_at DESC""", params)
        leads = [_row_to_dict(r) for r in cur.fetchall()]
    board = {}
    for s in stages:
        skey = s["stage_id"].replace("st_", "", 1)
        board[skey] = {"stage_id": s["stage_id"], "name": s["name"], "status": skey, "leads": []}
    for l in leads:
        st = l["status"]
        board.setdefault(st, {"stage_id": None, "name": st, "status": st, "leads": []})["leads"].append(l)
    ordered = [{"stage_id": s["stage_id"], "name": s["name"], "status": s["stage_id"].replace("st_", "", 1)} for s in stages]
    return {"stages": ordered, "board": board}



# ── 撞单工作台 + 合并 ─────────────────────────────────────────

@router.get("/collisions")
def collisions(user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    """疑似撞单：手机或微信相同的线索组。"""
    with db_cursor() as cur:
        cur.execute(
            """SELECT student_phone, student_wechat, COUNT(*) c
               FROM leads WHERE org_id=%s AND is_recycled=0
                 AND (student_phone IS NOT NULL AND student_phone != '' OR
                      student_wechat IS NOT NULL AND student_wechat != '')
               GROUP BY student_phone, student_wechat HAVING c > 1""", (org_id,))
        keys = cur.fetchall()
    if not keys:
        return {"groups": []}
    groups = []
    with db_cursor() as cur:
        for k in keys:
            sql = """SELECT lead_id, student_name, student_phone, student_wechat,
                           assigned_advisor_id, status, created_at, source
                    FROM leads WHERE org_id=%s AND is_recycled=0 AND ("""
            params = [org_id]
            conds = []
            if k["student_phone"]:
                conds.append("student_phone=%s"); params.append(k["student_phone"])
            if k["student_wechat"]:
                conds.append("student_wechat=%s"); params.append(k["student_wechat"])
            sql += " OR ".join(conds) + ") ORDER BY created_at"
            cur.execute(sql, params)
            leads = [_row_to_dict(r) for r in cur.fetchall()]
            if len(leads) > 1:
                groups.append({"key": k["student_phone"] or k["student_wechat"], "leads": leads})
    return {"groups": groups}


class MergeReq(BaseModel):
    keep_lead_id: str
    merge_lead_ids: list[str] = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


@router.post("/merge")
def merge_leads(req: MergeReq, user: dict = Depends(auth.require_owner),
                org_id: str = Depends(get_org_id)):
    """合并多条线索到 keep。owner 权限。被合并线索 is_recycled=1 归档，activity 迁移。"""
    with db_transaction() as cur:
        cur.execute("SELECT * FROM leads WHERE lead_id=%s AND org_id=%s", (req.keep_lead_id, org_id))
        keep = cur.fetchone()
        if not keep: raise HTTPException(404, "目标线索不存在")
        for mid in req.merge_lead_ids:
            cur.execute("SELECT * FROM leads WHERE lead_id=%s AND org_id=%s", (mid, org_id))
            dup = cur.fetchone()
            if not dup: raise HTTPException(404, f"被合并线索 {mid} 不存在")
            # 活动记录迁移
            cur.execute("UPDATE lead_activities SET lead_id=%s WHERE lead_id=%s", (req.keep_lead_id, mid))
            # 归档
            cur.execute(
                "UPDATE leads SET is_recycled=1, recycled_at=NOW(), recycled_reason=%s, status='lost' WHERE lead_id=%s",
                (f"merged to {req.keep_lead_id} ({req.reason})", mid))
        # 审计
        cur.execute(
            """INSERT INTO audit_log (id, org_id, actor_member_id, action, target_type, target_id, detail)
               VALUES (%s,%s,%s,'lead_merge','lead',%s,%s)""",
            (new_id(), org_id, user.get("member_id"), req.keep_lead_id,
             json.dumps({"merged": req.merge_lead_ids, "reason": req.reason}, ensure_ascii=False)))
    return {"ok": True, "kept": req.keep_lead_id, "merged": req.merge_lead_ids}



@router.get("/{lead_id}")
def lead_detail(lead_id: str, user: dict = Depends(auth.require_staff),
                org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM leads WHERE lead_id=%s AND org_id=%s", (lead_id, org_id))
        lead = cur.fetchone()
        if not lead:
            raise HTTPException(404, "线索不存在")
        if not _can_see_all(user) and lead["assigned_advisor_id"] != user.get("member_id"):
            raise HTTPException(403, "无权查看该线索")
        cur.execute("SELECT * FROM lead_activities WHERE lead_id=%s ORDER BY created_at DESC LIMIT 100", (lead_id,))
        activities = [_row_to_dict(a) for a in cur.fetchall()]
    return {"lead": _row_to_dict(lead), "activities": activities}


# ── 更新 / 推进 / 分配 / 认领 ──────────────────────────────────

class LeadUpdate(BaseModel):
    student_name: str | None = None
    student_phone: str | None = None
    student_wechat: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    parent_wechat: str | None = None
    gpa: float | None = None
    target_countries: list | None = None
    target_majors: list | None = None
    budget_range: str | None = None
    priority: int | None = None
    notes: str | None = None
    next_contact_at: datetime | None = None


def _check_lead_access(lead_id, user, org_id):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM leads WHERE lead_id=%s AND org_id=%s", (lead_id, org_id))
        lead = cur.fetchone()
    if not lead: raise HTTPException(404, "线索不存在")
    if not _can_see_all(user) and lead["assigned_advisor_id"] != user.get("member_id"):
        raise HTTPException(403, "无权操作该线索")
    return lead


@router.put("/{lead_id}")
def update_lead(lead_id: str, req: LeadUpdate, user: dict = Depends(auth.require_staff),
                org_id: str = Depends(get_org_id)):
    _check_lead_access(lead_id, user, org_id)
    fields, params = [], []
    for k, v in req.model_dump(exclude_none=True).items():
        if k in ("target_countries", "target_majors"):
            v = json.dumps(v)
        fields.append(f"{k}=%s")
        params.append(v)
    if not fields: return {"ok": True}
    params.append(lead_id)
    with db_cursor() as cur:
        cur.execute(f"UPDATE leads SET {', '.join(fields)} WHERE lead_id=%s", params)
    return {"ok": True}


class MoveStageReq(BaseModel):
    status: str
    lost_reason: str | None = None
    lost_detail: str | None = None


@router.post("/{lead_id}/move-stage")
def move_stage(lead_id: str, req: MoveStageReq, user: dict = Depends(auth.require_staff),
               org_id: str = Depends(get_org_id)):
    if req.status not in LEAD_STATUSES:
        raise HTTPException(400, f"无效阶段：{req.status}")
    lead = _check_lead_access(lead_id, user, org_id)
    old = lead["status"]
    # 流失必须填原因 + 备注 ≥ 10 字
    if req.status == "lost":
        if req.lost_reason not in LOST_REASONS:
            raise HTTPException(400, "请选择流失原因")
        if not req.lost_detail or len(req.lost_detail.strip()) < 10:
            raise HTTPException(400, "请填写 ≥10 字的流失备注")
    with db_transaction() as cur:
        cur.execute(
            "UPDATE leads SET status=%s, lost_reason=%s, lost_detail=%s WHERE lead_id=%s",
            (req.status, req.lost_reason, req.lost_detail, lead_id))
        cur.execute(
            """INSERT INTO lead_activities (activity_id, org_id, lead_id, activity_type,
                subject, actor_member_id, actor_name)
               VALUES (%s,%s,%s,'status_change',%s,%s,%s)""",
            (new_short_id("act_"), org_id, lead_id,
             f"阶段 {old} → {req.status}" + (f"（流失原因：{req.lost_reason}）" if req.status=="lost" else ""),
             user.get("member_id"), user.get("name")))
    return {"ok": True, "from": old, "to": req.status}


class AssignReq(BaseModel):
    advisor_id: str


@router.post("/{lead_id}/assign")
def assign_lead(lead_id: str, req: AssignReq, user: dict = Depends(auth.require_owner),
                org_id: str = Depends(get_org_id)):
    _check_lead_access(lead_id, user, org_id)
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name FROM members WHERE id=%s AND org_id=%s AND role='advisor'",
            (req.advisor_id, org_id))
        if not cur.fetchone():
            raise HTTPException(400, "目标顾问不存在")
        cur.execute("UPDATE leads SET assigned_advisor_id=%s, status=IF(status='recycled','new',status) WHERE lead_id=%s",
                    (req.advisor_id, lead_id))
    return {"ok": True}


# ── 公海认领 ─────────────────────────────────────────────────────

@router.post("/{lead_id}/claim")
def claim_lead(lead_id: str, user: dict = Depends(auth.require_staff),
               org_id: str = Depends(get_org_id)):
    """从公海认领线索。advisor 认领自己，owner 可代别人认领。"""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM leads WHERE lead_id=%s AND org_id=%s", (lead_id, org_id))
        lead = cur.fetchone()
        if not lead: raise HTTPException(404, "线索不存在")
        if lead["is_recycled"] != 1 and lead.get("assigned_advisor_id"):
            raise HTTPException(400, "该线索已有归属，可走'转移'而非'认领'")
        target = user.get("member_id") if user["role"] == auth.ROLE_ADVISOR else None
        if not target:
            raise HTTPException(400, "owner 认领需指定目标顾问")
        cur.execute(
            "UPDATE leads SET assigned_advisor_id=%s, is_recycled=0, status='new', last_contact_at=NULL WHERE lead_id=%s",
            (target, lead_id))
    return {"ok": True}


# ── 跟进活动 ────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    activity_type: str
    subject: str | None = None
    content: str | None = None
    contact_type: str | None = None
    outcome: str | None = None
    follow_up_required: bool = False
    follow_up_date: datetime | None = None


@router.post("/{lead_id}/activities")
def add_activity(lead_id: str, req: ActivityCreate, user: dict = Depends(auth.require_staff),
                 org_id: str = Depends(get_org_id)):
    _check_lead_access(lead_id, user, org_id)
    aid = new_short_id("act_")
    now = datetime.utcnow()
    with db_transaction() as cur:
        cur.execute(
            """INSERT INTO lead_activities
               (activity_id, org_id, lead_id, activity_type, subject, content, contact_type,
                outcome, follow_up_required, follow_up_date, actor_member_id, actor_name)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (aid, org_id, lead_id, req.activity_type, req.subject, req.content, req.contact_type,
             req.outcome, req.follow_up_required, req.follow_up_date,
             user.get("member_id"), user.get("name")))
        cur.execute(
            """UPDATE leads SET last_contact_at=%s,
                next_contact_at=COALESCE(%s, next_contact_at),
                status=IF(status='new','contacted',status), contacted_at=COALESCE(contacted_at,%s)
               WHERE lead_id=%s""",
            (now, req.follow_up_date, now, lead_id))
    return {"activity_id": aid}


# ── 转化 ────────────────────────────────────────────────────────

class ConvertReq(BaseModel):
    create_account: bool = False
    initial_password: str | None = None
    signed_by_member_id: str | None = None  # 家长代签


@router.post("/{lead_id}/convert")
def convert_lead(lead_id: str, req: ConvertReq, user: dict = Depends(auth.require_staff),
                 org_id: str = Depends(get_org_id)):
    lead = _check_lead_access(lead_id, user, org_id)
    if lead["status"] == "converted":
        raise HTTPException(400, "该线索已转化")

    student_member_id = new_id()
    account_id = None
    now = datetime.utcnow()
    with db_transaction() as cur:
        cur.execute(
            """INSERT INTO members (id, org_id, account_id, name, role, is_virtual, phone, wechat)
               VALUES (%s,%s,NULL,%s,'student',%s,%s,%s)""",
            (student_member_id, org_id, lead["student_name"], 0 if req.create_account else 1,
             lead["student_phone"], lead["student_wechat"]))
        if req.create_account:
            if not req.initial_password:
                raise HTTPException(400, "创建账号需 initial_password")
            account_id = new_id()
            username = lead["student_phone"] or f"stu_{student_member_id[:8]}"
            cur.execute(
                "INSERT INTO accounts (id, org_id, username, password_hash, phone) VALUES (%s,%s,%s,%s,%s)",
                (account_id, org_id, username, auth.hash_password(req.initial_password), lead["student_phone"]))
            cur.execute("UPDATE members SET account_id=%s, is_virtual=0 WHERE id=%s", (account_id, student_member_id))
        # 家长虚拟成员
        if lead.get("parent_name"):
            parent_member_id = new_id()
            cur.execute(
                """INSERT INTO members (id, org_id, account_id, name, role, is_virtual, phone, wechat)
                   VALUES (%s,%s,NULL,%s,'parent',1,%s,%s)""",
                (parent_member_id, org_id, lead["parent_name"], lead["parent_phone"], lead["parent_wechat"]))
            cur.execute(
                "INSERT INTO member_relationships (id, org_id, from_member_id, to_member_id, rel_type) VALUES (%s,%s,%s,%s,'guardian')",
                (new_id(), org_id, parent_member_id, student_member_id))
        cur.execute(
            "UPDATE leads SET status='converted', member_id=%s, account_id=%s, converted_at=%s WHERE lead_id=%s",
            (student_member_id, account_id, now, lead_id))
        cur.execute(
            """INSERT INTO lead_conversions
               (conversion_id, org_id, lead_id, from_status, member_id, account_id,
                conversion_type, triggered_by, triggered_at)
               VALUES (%s,%s,%s,%s,%s,%s,'manual',%s,%s)""",
            (new_short_id("cv_"), org_id, lead_id, lead["status"], student_member_id, account_id,
             user.get("member_id"), now))
    return {"member_id": student_member_id, "account_id": account_id}


# ── 漏斗 / 来源 ROI（报表由 reports.py 接管） ─────────────────

@router.get("/stats/funnel")
def funnel(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    where = "l.org_id=%s AND l.is_recycled=0"
    params = [org_id]
    if not _can_see_all(user):
        where += " AND l.assigned_advisor_id=%s"
        params.append(user.get("member_id"))
    with db_cursor() as cur:
        cur.execute(f"SELECT status, COUNT(*) AS c FROM leads l WHERE {where} GROUP BY status", params)
        by_status = {r["status"]: r["c"] for r in cur.fetchall()}
        cur.execute(f"SELECT source, COUNT(*) AS c FROM leads l WHERE {where} GROUP BY source", params)
        by_source = {r["source"] or "未知": r["c"] for r in cur.fetchall()}
    return {"by_status": by_status, "by_source": by_source}
