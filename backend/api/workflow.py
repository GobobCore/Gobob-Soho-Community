"""
api/workflow.py — 进程管理：申请 / 里程碑 / 任务 / 文档 / 推荐信 / 通知

学生端与机构端共用。学生/家长看自己的；员工按分配范围看。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor
from core.id_gen import new_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


def _row(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif hasattr(v, "isoformat") and not isinstance(v, str):
            d[k] = v.isoformat()
    return d


def _resolve_student(user: dict, org_id: str, member_id: str | None) -> str:
    """解析目标学生：学生本人/家长孩子/员工指定。"""
    if user["role"] in (auth.ROLE_OWNER, auth.ROLE_ADVISOR):
        if not member_id:
            raise HTTPException(400, "需指定 student_id")
        return member_id
    # 学生
    if user["role"] == auth.ROLE_STUDENT:
        return user.get("member_id")
    # 家长 → 孩子
    with db_cursor() as cur:
        cur.execute("SELECT to_member_id FROM member_relationships WHERE from_member_id=%s AND org_id=%s LIMIT 1",
                    (user.get("member_id"), org_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "未关联学生")
    return row["to_member_id"]


# ── 申请 ──────────────────────────────────────────────────────────

class AppCreate(BaseModel):
    student_id: str | None = None
    school_name: str = Field(..., min_length=1)
    gobob_school_id: str | None = None
    program_name: str | None = None
    degree: str | None = None
    deadline: str | None = None
    notes: str | None = None


@router.post("/applications")
def create_application(req: AppCreate, user: dict = Depends(auth.get_current_user),
                       org_id: str = Depends(get_org_id)):
    sid = _resolve_student(user, org_id, req.student_id)
    aid = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO applications (id, org_id, member_id, gobob_school_id, school_name,
               program_name, degree, deadline, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (aid, org_id, sid, req.gobob_school_id, req.school_name, req.program_name,
             req.degree, req.deadline, req.notes))
    return {"application_id": aid}


@router.get("/applications")
def list_applications(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id),
                      student_id: str | None = None):
    sid = _resolve_student(user, org_id, student_id)
    with db_cursor() as cur:
        cur.execute("SELECT * FROM applications WHERE member_id=%s AND org_id=%s ORDER BY deadline IS NULL, deadline",
                    (sid, org_id))
        rows = [_row(r) for r in cur.fetchall()]
    return {"items": rows}


class AppStatusReq(BaseModel):
    status: str
    result_type: str | None = None


@router.post("/applications/{aid}/status")
def update_application(aid: str, req: AppStatusReq, user: dict = Depends(auth.get_current_user),
                       org_id: str = Depends(get_org_id)):
    submitted = datetime.utcnow() if req.status == "submitted" else None
    with db_cursor() as cur:
        cur.execute(
            """UPDATE applications SET status=%s, result_type=COALESCE(%s,result_type),
               submitted_at=COALESCE(%s,submitted_at) WHERE id=%s AND org_id=%s""",
            (req.status, req.result_type, submitted, aid, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "申请不存在")
    return {"ok": True}


# ── 里程碑 ────────────────────────────────────────────────────────

class MilestoneCreate(BaseModel):
    student_id: str | None = None
    title: str = Field(..., min_length=1)
    category: str | None = None
    phase: str | None = None
    due_date: str | None = None
    sort_order: int = 0


@router.post("/milestones")
def create_milestone(req: MilestoneCreate, user: dict = Depends(auth.get_current_user),
                     org_id: str = Depends(get_org_id)):
    sid = _resolve_student(user, org_id, req.student_id)
    mid = new_id()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO milestones (id, org_id, member_id, title, category, phase, due_date, sort_order) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (mid, org_id, sid, req.title, req.category, req.phase, req.due_date, req.sort_order))
    return {"milestone_id": mid}


@router.get("/milestones")
def list_milestones(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id),
                    student_id: str | None = None):
    sid = _resolve_student(user, org_id, student_id)
    with db_cursor() as cur:
        cur.execute("SELECT * FROM milestones WHERE member_id=%s AND org_id=%s ORDER BY sort_order, due_date IS NULL, due_date",
                    (sid, org_id))
        rows = [_row(r) for r in cur.fetchall()]
    return {"items": rows}


class DoneReq(BaseModel):
    status: str  # pending/in_progress/done/cancelled


@router.post("/milestones/{mid}/status")
def update_milestone(mid: str, req: DoneReq, user: dict = Depends(auth.get_current_user),
                     org_id: str = Depends(get_org_id)):
    completed = datetime.utcnow() if req.status == "done" else None
    with db_cursor() as cur:
        cur.execute("UPDATE milestones SET status=%s, completed_at=COALESCE(%s,completed_at) WHERE id=%s AND org_id=%s",
                    (req.status, completed, mid, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "里程碑不存在")
    return {"ok": True}


# ── 任务 ──────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    student_id: str | None = None
    title: str = Field(..., min_length=1)
    description: str | None = None
    phase: str | None = None
    milestone_id: str | None = None
    assignee_type: str = "student"
    assignee_member_id: str | None = None
    due_date: str | None = None
    sort_order: int = 0


@router.post("/tasks")
def create_task(req: TaskCreate, user: dict = Depends(auth.get_current_user),
                org_id: str = Depends(get_org_id)):
    sid = _resolve_student(user, org_id, req.student_id)
    tid = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO tasks (id, org_id, member_id, milestone_id, title, description, phase,
               assignee_type, assignee_member_id, due_date, sort_order)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (tid, org_id, sid, req.milestone_id, req.title, req.description, req.phase,
             req.assignee_type, req.assignee_member_id, req.due_date, req.sort_order))
    return {"task_id": tid}


@router.get("/tasks")
def list_tasks(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id),
               student_id: str | None = None, status: str | None = None):
    sid = _resolve_student(user, org_id, student_id)
    where = ["member_id=%s", "org_id=%s"]
    params = [sid, org_id]
    if status:
        where.append("status=%s")
        params.append(status)
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM tasks WHERE {' AND '.join(where)} ORDER BY sort_order, due_date IS NULL, due_date",
                    params)
        rows = [_row(r) for r in cur.fetchall()]
    return {"items": rows}


@router.post("/tasks/{tid}/status")
def update_task(tid: str, req: DoneReq, user: dict = Depends(auth.get_current_user),
                org_id: str = Depends(get_org_id)):
    completed = datetime.utcnow() if req.status == "done" else None
    with db_cursor() as cur:
        cur.execute("UPDATE tasks SET status=%s, completed_at=COALESCE(%s,completed_at) WHERE id=%s AND org_id=%s",
                    (req.status, completed, tid, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "任务不存在")
    return {"ok": True}


# ── 通知 ──────────────────────────────────────────────────────────

@router.get("/notifications")
def list_notifications(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id),
                       unread_only: bool = False):
    where = ["member_id=%s", "org_id=%s"]
    params = [user.get("member_id"), org_id]
    if unread_only:
        where.append("is_read=0")
    with db_cursor() as cur:
        cur.execute(f"SELECT * FROM notifications WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT 100",
                    params)
        rows = [_row(r) for r in cur.fetchall()]
    return {"items": rows}


@router.post("/notifications/{nid}/read")
def read_notification(nid: str, user: dict = Depends(auth.get_current_user),
                      org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("UPDATE notifications SET is_read=1 WHERE id=%s AND member_id=%s AND org_id=%s",
                    (nid, user.get("member_id"), org_id))
    return {"ok": True}
