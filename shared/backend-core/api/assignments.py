"""
api/assignments.py — 老师分配 + 换师 + 交付物

按环节（phase）给学生分配老师：overall/exam/writing/school/interview/visa/other。
换师：关闭旧 assignment（status=transferred）+ 新建 assignment + 交接说明 + 通知新老师/学生/家长。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id, new_short_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/assignments", tags=["assignments"])

PHASES = {"overall", "exam", "writing", "school", "interview", "visa", "other"}


def _row(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _notify(cur, org_id, member_id, title, content, ntype):
    cur.execute(
        "INSERT INTO notifications (id, org_id, member_id, title, content, type) VALUES (%s,%s,%s,%s,%s,%s)",
        (new_id(), org_id, member_id, title, content, ntype))


# ── 分配老师 ──────────────────────────────────────────────────────

class AssignCreate(BaseModel):
    student_member_id: str
    advisor_member_id: str
    phase: str = "overall"


@router.post("")
def create_assignment(req: AssignCreate, user: dict = Depends(auth.require_staff),
                      org_id: str = Depends(get_org_id)):
    if req.phase not in PHASES:
        raise HTTPException(400, f"无效环节：{req.phase}")
    with db_cursor() as cur:
        cur.execute("SELECT id, name FROM members WHERE id=%s AND org_id=%s AND role='student'",
                    (req.student_member_id, org_id))
        stu = cur.fetchone()
        if not stu:
            raise HTTPException(400, "学生不存在")
        cur.execute("SELECT id, name FROM members WHERE id=%s AND org_id=%s AND role='advisor'",
                    (req.advisor_member_id, org_id))
        adv = cur.fetchone()
        if not adv:
            raise HTTPException(400, "老师不存在")
        # 同学生同环节是否已有 active 分配
        cur.execute(
            """SELECT id FROM service_assignments
               WHERE org_id=%s AND student_member_id=%s AND phase=%s AND status IN ('pending','active')""",
            (org_id, req.student_member_id, req.phase))
        if cur.fetchone():
            raise HTTPException(400, "该学生在此环节已有负责老师，请用换师接口")
        aid = new_id()
        cur.execute(
            """INSERT INTO service_assignments
               (id, org_id, student_member_id, advisor_member_id, phase, status, started_at, created_by)
               VALUES (%s,%s,%s,%s,%s,'active',%s,%s)""",
            (aid, org_id, req.student_member_id, req.advisor_member_id, req.phase,
             datetime.utcnow(), user.get("member_id")))
    return {"assignment_id": aid}


# ── 换师（核心差异化功能）─────────────────────────────────────────

class HandoverReq(BaseModel):
    new_advisor_id: str
    handover_note: str = Field(..., min_length=1, description="交接说明（必填）")


@router.post("/{assignment_id}/handover")
def handover(assignment_id: str, req: HandoverReq,
             user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    """换师：旧 assignment → transferred，新建 assignment，三方通知 + 审计。"""
    with db_transaction() as cur:
        cur.execute(
            """SELECT a.*, s.name AS student_name, o.name AS old_advisor_name
               FROM service_assignments a
               LEFT JOIN members s ON s.id=a.student_member_id
               LEFT JOIN members o ON o.id=a.advisor_member_id
               WHERE a.id=%s AND a.org_id=%s""",
            (assignment_id, org_id))
        old = cur.fetchone()
        if not old:
            raise HTTPException(404, "分配不存在")
        if old["status"] not in ("pending", "active"):
            raise HTTPException(400, f"当前状态 {old['status']} 不能换师")
        cur.execute("SELECT id, name FROM members WHERE id=%s AND org_id=%s AND role='advisor'",
                    (req.new_advisor_id, org_id))
        new_adv = cur.fetchone()
        if not new_adv:
            raise HTTPException(400, "新老师不存在")

        new_aid = new_id()
        now = datetime.utcnow()
        # 关闭旧
        cur.execute(
            """UPDATE service_assignments
               SET status='transferred', transferred_to=%s, handover_note=%s, completed_at=%s
               WHERE id=%s""",
            (new_aid, req.handover_note, now, assignment_id))
        # 新建
        cur.execute(
            """INSERT INTO service_assignments
               (id, org_id, student_member_id, advisor_member_id, phase, status, started_at, created_by)
               VALUES (%s,%s,%s,%s,%s,'active',%s,%s)""",
            (new_aid, org_id, old["student_member_id"], req.new_advisor_id, old["phase"],
             now, user.get("member_id")))

        phase = old["phase"]
        sname = old["student_name"] or "学生"
        # 通知新老师
        _notify(cur, org_id, req.new_advisor_id, f"接手学生 {sname}（{phase}）",
                f"你从 {old['old_advisor_name']} 接手了学生 {sname} 的 {phase} 环节。\n交接说明：{req.handover_note}",
                "handover")
        # 通知学生
        _notify(cur, org_id, old["student_member_id"], "服务老师已更换",
                f"你的 {phase} 环节服务老师已由 {old['old_advisor_name']} 更换为 {new_adv['name']}。",
                "handover")
        # 通知关联家长
        cur.execute("SELECT from_member_id FROM member_relationships WHERE to_member_id=%s AND org_id=%s",
                    (old["student_member_id"], org_id))
        for p in cur.fetchall():
            _notify(cur, org_id, p["from_member_id"], "孩子服务老师已更换",
                    f"您孩子的 {phase} 环节老师已更换为 {new_adv['name']}。", "handover")
        # 审计
        cur.execute(
            """INSERT INTO audit_log (id, org_id, actor_member_id, action, target_type, target_id, detail)
               VALUES (%s,%s,%s,'handover','assignment',%s,%s)""",
            (new_id(), org_id, user.get("member_id"), new_aid,
             json.dumps({"student": old["student_member_id"], "phase": phase,
                         "from": old["advisor_member_id"], "to": req.new_advisor_id,
                         "note": req.handover_note}, ensure_ascii=False)))
    return {"new_assignment_id": new_aid}


class StatusReq(BaseModel):
    status: str  # active/completed/cancelled


@router.post("/{assignment_id}/status")
def update_assignment_status(assignment_id: str, req: StatusReq,
                             user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    if req.status not in ("active", "completed", "cancelled"):
        raise HTTPException(400, "无效状态")
    completed = datetime.utcnow() if req.status == "completed" else None
    with db_cursor() as cur:
        cur.execute(
            "UPDATE service_assignments SET status=%s, completed_at=COALESCE(%s,completed_at) WHERE id=%s AND org_id=%s",
            (req.status, completed, assignment_id, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "分配不存在")
    return {"ok": True}


# ── 查询 ──────────────────────────────────────────────────────────

@router.get("")
def list_assignments(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id),
                     student_id: str | None = None, advisor_id: str | None = None,
                     status: str | None = None, page: int = Query(1, ge=1),
                     page_size: int = Query(50, ge=1, le=200)):
    where = ["a.org_id=%s"]
    params = [org_id]
    # advisor 默认只看自己的（除非 owner 或显式查别人）
    if user["role"] == auth.ROLE_ADVISOR and not advisor_id:
        where.append("a.advisor_member_id=%s")
        params.append(user.get("member_id"))
    if student_id:
        where.append("a.student_member_id=%s")
        params.append(student_id)
    if advisor_id:
        where.append("a.advisor_member_id=%s")
        params.append(advisor_id)
    if status:
        where.append("a.status=%s")
        params.append(status)
    sql_where = " AND ".join(where)
    offset = (page - 1) * page_size
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM service_assignments a WHERE {sql_where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT a.*, s.name AS student_name, adv.name AS advisor_name
                FROM service_assignments a
                LEFT JOIN members s ON s.id=a.student_member_id
                LEFT JOIN members adv ON adv.id=a.advisor_member_id
                WHERE {sql_where} ORDER BY a.updated_at DESC LIMIT %s OFFSET %s""",
            params + [page_size, offset])
        rows = [_row(r) for r in cur.fetchall()]
    return {"total": total, "items": rows}


# ── 交付物 ────────────────────────────────────────────────────────

class DeliverableCreate(BaseModel):
    student_member_id: str
    assignment_id: str | None = None
    title: str = Field(..., min_length=1)
    module_code: str | None = None
    content: str | None = None
    file_url: str | None = None


@router.post("/deliverables")
def create_deliverable(req: DeliverableCreate, user: dict = Depends(auth.require_staff),
                       org_id: str = Depends(get_org_id)):
    """建交付物骨架（d1），同时落首个版本 v1（draft 状态）。"""
    did = new_id()
    vid = new_id()
    with db_transaction() as cur:
        cur.execute(
            """INSERT INTO deliverables
               (id, org_id, assignment_id, student_member_id, advisor_member_id, title,
                module_code, status, content, file_url, current_version_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s)""",
            (did, org_id, req.assignment_id, req.student_member_id, user.get("member_id"),
             req.title, req.module_code, req.content, req.file_url, vid))
        cur.execute(
            """INSERT INTO deliverable_versions
               (id, org_id, deliverable_id, version, content, file_url, submitted_by)
               VALUES (%s,%s,%s,1,%s,%s,%s)""",
            (vid, org_id, did, req.content, req.file_url, user.get("member_id")))
    return {"deliverable_id": did, "version_id": vid, "version": 1}


class DeliverableVersionReq(BaseModel):
    content: str | None = None
    file_url: str | None = None
    submit: bool = False  # True=提交审阅（draft → in_review）


@router.post("/deliverables/{did}/versions")
def new_version(did: str, req: DeliverableVersionReq,
                user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    """出 v2/v3... 版本。submit=True 时状态变 in_review 并写 submit_at。"""
    with db_transaction() as cur:
        cur.execute("SELECT * FROM deliverables WHERE id=%s AND org_id=%s", (did, org_id))
        d = cur.fetchone()
        if not d: raise HTTPException(404, "交付物不存在")
        # 当前最大版本
        cur.execute(
            "SELECT COALESCE(MAX(version),0)+1 AS next FROM deliverable_versions WHERE deliverable_id=%s",
            (did,))
        v = cur.fetchone()["next"]
        vid = new_id()
        now = datetime.utcnow() if req.submit else None
        cur.execute(
            """INSERT INTO deliverable_versions
               (id, org_id, deliverable_id, version, content, file_url, submitted_by, submitted_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (vid, org_id, did, v, req.content, req.file_url, user.get("member_id"), now))
        new_status = "in_review" if req.submit else "draft"
        cur.execute(
            """UPDATE deliverables
               SET current_version_id=%s, status=%s,
                   content=COALESCE(%s,content), file_url=COALESCE(%s,file_url),
                   submitted_at=COALESCE(%s,submitted_at)
               WHERE id=%s""",
            (vid, new_status, req.content, req.file_url, now, did))
    return {"version_id": vid, "version": v, "status": new_status}


class DeliverableReviewReq(BaseModel):
    decision: str  # approve/reject/comment
    content: str = Field(..., min_length=1)


@router.post("/deliverables/versions/{vid}/review")
def review_version(vid: str, req: DeliverableReviewReq,
                   user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    """审阅版本：approve→accepted 关联 contract_items；reject→状态回 draft；comment→保留状态。"""
    if req.decision not in ("approve", "reject", "comment"):
        raise HTTPException(400, "无效决策")
    with db_transaction() as cur:
        cur.execute(
            """SELECT v.*, d.id AS d_id, d.status, d.student_member_id, d.module_code
               FROM deliverable_versions v JOIN deliverables d ON d.id=v.deliverable_id
               WHERE v.id=%s AND v.org_id=%s""", (vid, org_id))
        v = cur.fetchone()
        if not v: raise HTTPException(404, "版本不存在")
        cur.execute(
            """INSERT INTO deliverable_comments
               (id, org_id, version_id, reviewer_member_id, reviewer_name, content, decision)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (new_id(), org_id, vid, user.get("member_id"), user.get("name"),
             req.content, req.decision))
        if req.decision == "approve":
            cur.execute("UPDATE deliverables SET status='accepted' WHERE id=%s", (v["d_id"],))
            # 关联 contract_items：找到该学生该 module_code 的 pending 项 → completed
            cur.execute(
                """UPDATE contract_items
                   SET status='completed', completed_at=NOW(), deliverable_id=%s
                   WHERE org_id=%s AND student_member_id=%s
                     AND module_code=%s AND status IN ('pending','in_progress','delivered')
                   LIMIT 1""",
                (v["d_id"], org_id, v["student_member_id"], v.get("module_code")))
        elif req.decision == "reject":
            # reject 必须有 comment（已强制 min_length=1）
            cur.execute("UPDATE deliverables SET status='draft' WHERE id=%s", (v["d_id"],))
    return {"ok": True, "decision": req.decision}


@router.get("/deliverables/{did}")
def deliverable_detail(did: str, user: dict = Depends(auth.get_current_user),
                       org_id: str = Depends(get_org_id)):
    """返回交付物 + 全版本 + 审阅意见。"""
    with db_cursor() as cur:
        cur.execute(
            """SELECT d.*, adv.name AS advisor_name FROM deliverables d
               LEFT JOIN members adv ON adv.id=d.advisor_member_id
               WHERE d.id=%s AND d.org_id=%s""", (did, org_id))
        d = cur.fetchone()
        if not d: raise HTTPException(404, "交付物不存在")
        cur.execute(
            """SELECT v.*, mem.name AS submitted_by_name FROM deliverable_versions v
               LEFT JOIN members mem ON mem.id=v.submitted_by
               WHERE v.deliverable_id=%s ORDER BY v.version""", (did,))
        versions = []
        for v in cur.fetchall():
            cur.execute(
                """SELECT c.*, mem.name AS reviewer_name FROM deliverable_comments c
                   LEFT JOIN members mem ON mem.id=c.reviewer_member_id
                   WHERE c.version_id=%s ORDER BY c.created_at""", (v["id"],))
            v["comments"] = [_row(c) for c in cur.fetchall()]
            versions.append(_row(v))
    return {"deliverable": _row(d), "versions": versions}


@router.get("/deliverables")
def list_deliverables(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id),
                      student_id: str | None = None):
    where = ["d.org_id=%s"]
    params = [org_id]
    if user["role"] == auth.ROLE_STUDENT:
        where.append("d.student_member_id=%s")
        params.append(user.get("member_id"))
    elif student_id:
        where.append("d.student_member_id=%s")
        params.append(student_id)
    sql_where = " AND ".join(where)
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT d.id, d.title, d.module_code, d.status, d.current_version_id,
                       d.updated_at, adv.name AS advisor_name, s.name AS student_name
                FROM deliverables d
                LEFT JOIN members adv ON adv.id=d.advisor_member_id
                LEFT JOIN members s ON s.id=d.student_member_id
                WHERE {sql_where} ORDER BY d.updated_at DESC""", params)
        rows = [_row(r) for r in cur.fetchall()]
    return {"items": rows}
