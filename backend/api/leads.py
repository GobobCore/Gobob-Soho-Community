"""
api/leads.py — 线索池（CRM 生源管理）

线索 → 跟进 → 转化 → 签约。看板 + 漏斗 + 分配。
机构员工（owner/advisor）用；owner 看全机构，advisor 只看自己名下。

转化：线索 → 创建学生 member（默认 is_virtual 虚拟成员，机构代管）。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id, new_short_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/leads", tags=["leads"])

LEAD_STATUSES = {"new", "contacted", "qualified", "proposal", "negotiation", "converted", "lost"}


def _can_see_all(user: dict) -> bool:
    return user.get("role") == auth.ROLE_OWNER


def _row_to_dict(row) -> dict:
    d = dict(row)
    for k in ("target_countries", "target_degrees", "target_majors", "tags", "team_members"):
        if d.get(k) and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


# ── 创建 ─────────────────────────────────────────────────────────

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
    lead_id = new_short_id("lead_")
    advisor = req.assigned_advisor_id or user.get("member_id")
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
    return {"lead_id": lead_id, "status": "new"}


# 获客门户留资（匿名，无鉴权）。source 固定 assessment，归默认机构。
@router.post("/capture")
def capture_lead(req: LeadCreate):
    lead_id = new_short_id("lead_")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM orgs ORDER BY created_at LIMIT 1")
        org = cur.fetchone()
        if not org:
            raise HTTPException(503, "系统未初始化")
        cur.execute(
            """INSERT INTO leads
               (lead_id, org_id, student_name, student_phone, student_wechat, student_email,
                target_countries, target_degrees, target_majors, source, source_detail, status,
                assessment_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'assessment',%s,'new',%s)""",
            (lead_id, org["id"], req.student_name, req.student_phone, req.student_wechat,
             req.student_email,
             json.dumps(req.target_countries) if req.target_countries else None,
             json.dumps(req.target_degrees) if req.target_degrees else None,
             json.dumps(req.target_majors) if req.target_majors else None,
             req.source_detail, req.assessment_id),
        )
    return {"lead_id": lead_id, "ok": True}


# ── 列表 / 看板 ───────────────────────────────────────────────────

@router.get("")
def list_leads(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id),
               status: str | None = None, q: str | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    where = ["l.org_id=%s", "l.is_recycled=0"]
    params = [org_id]
    if not _can_see_all(user):  # advisor 只看自己名下
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
                ORDER BY l.created_at DESC LIMIT %s OFFSET %s""",
            params + [page_size, offset],
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
    return {"total": total, "page": page, "items": rows}


@router.get("/board")
def pipeline_board(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    """看板：按 pipeline 阶段分组（stage 用 status 键关联，而非中文名）。"""
    where = "l.org_id=%s AND l.is_recycled=0"
    params = [org_id]
    if not _can_see_all(user):
        where += " AND l.assigned_advisor_id=%s"
        params.append(user.get("member_id"))
    # stage_id 形如 st_new → 线索 status 键 'new'
    with db_cursor() as cur:
        cur.execute(
            "SELECT stage_id, name, sort_order FROM lead_pipeline_stages WHERE org_id=%s ORDER BY sort_order",
            (org_id,),
        )
        stages = cur.fetchall()
        cur.execute(
            f"""SELECT l.lead_id, l.student_name, l.status, l.priority, l.source,
                       l.next_contact_at, m.name AS advisor_name
                FROM leads l LEFT JOIN members m ON m.id=l.assigned_advisor_id
                WHERE {where} ORDER BY l.priority DESC, l.updated_at DESC""",
            params,
        )
        leads = [_row_to_dict(r) for r in cur.fetchall()]
    # stage_id 'st_new' → status 'new'；每个阶段容器挂 status 键
    board = {}
    for s in stages:
        skey = s["stage_id"].replace("st_", "", 1)
        board[skey] = {"stage_id": s["stage_id"], "name": s["name"], "status": skey, "leads": []}
    for l in leads:
        st = l["status"]
        board.setdefault(st, {"stage_id": None, "name": st, "status": st, "leads": []})["leads"].append(l)
    # 输出有序阶段（含 status 键）
    ordered = [{"stage_id": s["stage_id"], "name": s["name"], "status": s["stage_id"].replace("st_", "", 1)} for s in stages]
    return {"stages": ordered, "board": board}


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
        cur.execute(
            "SELECT * FROM lead_activities WHERE lead_id=%s ORDER BY created_at DESC LIMIT 100",
            (lead_id,),
        )
        activities = [_row_to_dict(a) for a in cur.fetchall()]
    return {"lead": _row_to_dict(lead), "activities": activities}


# ── 更新 / 阶段推进 / 分配 ────────────────────────────────────────

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


def _check_lead_access(lead_id: str, user: dict, org_id: str) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM leads WHERE lead_id=%s AND org_id=%s", (lead_id, org_id))
        lead = cur.fetchone()
    if not lead:
        raise HTTPException(404, "线索不存在")
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
    if not fields:
        return {"ok": True}
    params.append(lead_id)
    with db_cursor() as cur:
        cur.execute(f"UPDATE leads SET {', '.join(fields)} WHERE lead_id=%s", params)
    return {"ok": True}


class MoveStageReq(BaseModel):
    status: str


@router.post("/{lead_id}/move-stage")
def move_stage(lead_id: str, req: MoveStageReq, user: dict = Depends(auth.require_staff),
               org_id: str = Depends(get_org_id)):
    if req.status not in LEAD_STATUSES:
        raise HTTPException(400, f"无效阶段：{req.status}")
    lead = _check_lead_access(lead_id, user, org_id)
    old = lead["status"]
    with db_transaction() as cur:
        cur.execute("UPDATE leads SET status=%s WHERE lead_id=%s", (req.status, lead_id))
        cur.execute(
            """INSERT INTO lead_activities (activity_id, org_id, lead_id, activity_type,
                subject, actor_member_id, actor_name)
               VALUES (%s,%s,%s,'status_change',%s,%s,%s)""",
            (new_short_id("act_"), org_id, lead_id, f"阶段 {old} → {req.status}",
             user.get("member_id"), user.get("name")),
        )
    return {"ok": True, "from": old, "to": req.status}


class AssignReq(BaseModel):
    advisor_id: str


@router.post("/{lead_id}/assign")
def assign_lead(lead_id: str, req: AssignReq, user: dict = Depends(auth.require_owner),
                org_id: str = Depends(get_org_id)):
    """分配/转移归属（owner 权限）。"""
    _check_lead_access(lead_id, user, org_id)
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name FROM members WHERE id=%s AND org_id=%s AND role='advisor'",
            (req.advisor_id, org_id),
        )
        if not cur.fetchone():
            raise HTTPException(400, "目标顾问不存在")
        cur.execute("UPDATE leads SET assigned_advisor_id=%s WHERE lead_id=%s", (req.advisor_id, lead_id))
    return {"ok": True}


# ── 跟进活动 ──────────────────────────────────────────────────────

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
             user.get("member_id"), user.get("name")),
        )
        # 更新线索的最后/下次联系时间
        cur.execute(
            """UPDATE leads SET last_contact_at=%s,
                next_contact_at=COALESCE(%s, next_contact_at),
                status=IF(status='new','contacted',status), contacted_at=COALESCE(contacted_at,%s)
               WHERE lead_id=%s""",
            (now, req.follow_up_date, now, lead_id),
        )
    return {"activity_id": aid}


# ── 转化：线索 → 学生成员 ─────────────────────────────────────────

class ConvertReq(BaseModel):
    create_account: bool = False  # 是否同时建登录账号（学生/家长可登录）
    initial_password: str | None = None


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
        # 学生虚拟成员
        cur.execute(
            """INSERT INTO members (id, org_id, account_id, name, role, is_virtual, phone, wechat)
               VALUES (%s,%s,NULL,%s,'student',%s,%s,%s)""",
            (student_member_id, org_id, lead["student_name"], 0 if req.create_account else 1,
             lead["student_phone"], lead["student_wechat"]),
        )
        # 可选：建登录账号
        if req.create_account:
            if not req.initial_password:
                raise HTTPException(400, "创建账号需 initial_password")
            account_id = new_id()
            username = lead["student_phone"] or f"stu_{student_member_id[:8]}"
            cur.execute(
                "INSERT INTO accounts (id, org_id, username, password_hash, phone) VALUES (%s,%s,%s,%s,%s)",
                (account_id, org_id, username, auth.hash_password(req.initial_password), lead["student_phone"]),
            )
            cur.execute("UPDATE members SET account_id=%s, is_virtual=0 WHERE id=%s",
                        (account_id, student_member_id))
        # 家长虚拟成员 + 关联（若有家长信息）
        if lead.get("parent_name"):
            parent_member_id = new_id()
            cur.execute(
                """INSERT INTO members (id, org_id, account_id, name, role, is_virtual, phone, wechat)
                   VALUES (%s,%s,NULL,%s,'parent',1,%s,%s)""",
                (parent_member_id, org_id, lead["parent_name"], lead["parent_phone"], lead["parent_wechat"]),
            )
            cur.execute(
                "INSERT INTO member_relationships (id, org_id, from_member_id, to_member_id) VALUES (%s,%s,%s,%s)",
                (new_id(), org_id, parent_member_id, student_member_id),
            )
        # 回写线索
        cur.execute(
            """UPDATE leads SET status='converted', member_id=%s, account_id=%s,
                converted_at=%s WHERE lead_id=%s""",
            (student_member_id, account_id, now, lead_id),
        )
        # 转化记录
        cur.execute(
            """INSERT INTO lead_conversions
               (conversion_id, org_id, lead_id, from_status, member_id, account_id,
                conversion_type, triggered_by, triggered_at)
               VALUES (%s,%s,%s,%s,%s,%s,'manual',%s,%s)""",
            (new_short_id("cv_"), org_id, lead_id, lead["status"], student_member_id,
             account_id, user.get("member_id"), now),
        )
    return {"member_id": student_member_id, "account_id": account_id}


# ── 漏斗 / 报表 ───────────────────────────────────────────────────

@router.get("/stats/funnel")
def funnel(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    where = "org_id=%s AND is_recycled=0"
    params = [org_id]
    if not _can_see_all(user):
        where += " AND assigned_advisor_id=%s"
        params.append(user.get("member_id"))
    with db_cursor() as cur:
        cur.execute(
            f"SELECT status, COUNT(*) AS c FROM leads WHERE {where} GROUP BY status", params)
        by_status = {r["status"]: r["c"] for r in cur.fetchall()}
        cur.execute(
            f"SELECT source, COUNT(*) AS c FROM leads WHERE {where} GROUP BY source", params)
        by_source = {r["source"] or "未知": r["c"] for r in cur.fetchall()}
    return {"by_status": by_status, "by_source": by_source}
