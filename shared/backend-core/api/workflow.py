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
    """解析目标学生：学生本人/家长孩子（可指定）/员工指定。

    员工/学生：member_id 指定或默认自己。
    家长：member_id 不传 → 默认第一个关联学生；传了则校验是否关联（防越权）。
    """
    if user["role"] in (auth.ROLE_OWNER, auth.ROLE_ADVISOR):
        if not member_id:
            raise HTTPException(400, "需指定 student_id")
        return member_id
    if user["role"] == auth.ROLE_STUDENT:
        return user.get("member_id")
    # 家长：可指定某个孩子（多孩子场景）
    if member_id:
        with db_cursor() as cur:
            cur.execute(
                """SELECT 1 FROM member_relationships
                   WHERE from_member_id=%s AND to_member_id=%s AND org_id=%s""",
                (user.get("member_id"), member_id, org_id))
            if not cur.fetchone():
                raise HTTPException(403, "该学生与你无关联")
        return member_id
    # 默认第一个孩子
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
    """状态切换：勾 done 时校验 task_dependencies（hard 必选完成；soft 仅警告）"""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM tasks WHERE id=%s AND org_id=%s", (tid, org_id))
        t = cur.fetchone()
        if not t: raise HTTPException(404, "任务不存在")
        warnings = []
        if req.status == "done":
            # hard 依赖：未完成 → 422
            cur.execute(
                """SELECT t2.id, t2.title, td.type
                   FROM task_dependencies td
                   JOIN tasks t2 ON t2.id=td.depends_on
                   WHERE td.task_id=%s AND td.type='hard' AND t2.status != 'done'""", (tid,))
            blocking = cur.fetchall()
            if blocking:
                names = [b["title"] for b in blocking]
                raise HTTPException(422, f"硬依赖未完成：{' / '.join(names)}")
            # soft 依赖：未完成 → warning（可放行）
            cur.execute(
                """SELECT t2.title, td.type FROM task_dependencies td
                   JOIN tasks t2 ON t2.id=td.depends_on
                   WHERE td.task_id=%s AND td.type='soft' AND t2.status != 'done'""", (tid,))
            softs = cur.fetchall()
            for s in softs:
                warnings.append(f"软依赖未完成：{s['title']}（仅提醒）")
        completed = datetime.utcnow() if req.status == "done" else None
        cur.execute(
            "UPDATE tasks SET status=%s, completed_at=COALESCE(%s,completed_at) WHERE id=%s AND org_id=%s",
            (req.status, completed, tid, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "任务不存在")
    return {"ok": True, "warnings": warnings}


# ── 任务依赖管理 ──────────────────────────────────────────────

class TaskDepReq(BaseModel):
    depends_on: str  # 前置任务 id
    type: str = "hard"  # hard/soft


@router.post("/tasks/{tid}/dependencies")
def add_dep(tid: str, req: TaskDepReq, user: dict = Depends(auth.require_staff),
            org_id: str = Depends(get_org_id)):
    """加依赖。写时做 DFS 环检测：若加这条形成环则 422。"""
    with db_cursor() as cur:
        cur.execute("SELECT id FROM tasks WHERE id=%s AND org_id=%s", (tid, org_id))
        if not cur.fetchone(): raise HTTPException(404, "任务不存在")
        if tid == req.depends_on:
            raise HTTPException(400, "不能依赖自己")
        cur.execute("SELECT id FROM tasks WHERE id=%s AND org_id=%s", (req.depends_on, org_id))
        if not cur.fetchone(): raise HTTPException(404, "被依赖任务不存在")
        # 环检测：新边 tid→req.depends_on 后，req.depends_on 是否能（直接或间接）回溯到 tid
        stack = [req.depends_on]
        seen = set()
        while stack:
            cur_id = stack.pop()
            if cur_id in seen: continue
            seen.add(cur_id)
            cur.execute("SELECT depends_on FROM task_dependencies WHERE task_id=%s", (cur_id,))
            for r in cur.fetchall():
                if r["depends_on"] == tid:
                    raise HTTPException(422, f"加这条依赖会形成环（{req.depends_on} 已依赖 {tid}）")
                stack.append(r["depends_on"])
        cur.execute(
            "INSERT IGNORE INTO task_dependencies (id, org_id, task_id, depends_on, type) VALUES (%s,%s,%s,%s,%s)",
            (new_id(), org_id, tid, req.depends_on, req.type))
    return {"ok": True}


@router.get("/tasks/{tid}/dependencies")
def list_deps(tid: str, user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM task_dependencies WHERE task_id=%s", (tid,))
        deps = [_row(d) for d in cur.fetchall()]
        # 反向：谁依赖我
        cur.execute("SELECT task_id, type FROM task_dependencies WHERE depends_on=%s", (tid,))
        reverse = [_row(d) for d in cur.fetchall()]
    return {"dependencies": deps, "depended_by": reverse}


# ── 时间线（Gantt 简化版） ─────────────────────────────────────

@router.get("/timeline")
def timeline(student_id: str, user: dict = Depends(auth.get_current_user),
             org_id: str = Depends(get_org_id)):
    """返回学生所有任务的 phase 分组 + 关键路径 + 下个卡点。"""
    with db_cursor() as cur:
        cur.execute(
            "SELECT id FROM members WHERE id=%s AND org_id=%s AND role='student'",
            (student_id, org_id))
        if not cur.fetchone(): raise HTTPException(404, "学生不存在")
        cur.execute(
            """SELECT id, title, phase, status, due_date, sort_order
               FROM tasks WHERE member_id=%s AND org_id=%s
               ORDER BY COALESCE(due_date,'9999-12-31'), sort_order""", (student_id, org_id))
        tasks = [_row(t) for t in cur.fetchall()]
        # 依赖图
        cur.execute(
            "SELECT task_id, depends_on, type FROM task_dependencies WHERE org_id=%s", (org_id,))
        deps = cur.fetchall()

    by_phase = {}
    for t in tasks:
        by_phase.setdefault(t.get("phase") or "other", []).append(t)

    # 各阶段起止
    phases = []
    for phase, items in by_phase.items():
        due_dates = [t["due_date"] for t in items if t.get("due_date")]
        phases.append({
            "phase": phase,
            "task_count": len(items),
            "done_count": sum(1 for t in items if t["status"] == "done"),
            "start": min(due_dates) if due_dates else None,
            "end": max(due_dates) if due_dates else None,
            "progress": round(sum(1 for t in items if t["status"] == "done") / len(items), 2) if items else 0,
        })

    # 关键路径：拓扑 + 找含 hard 依赖的最长链
    from collections import defaultdict
    succ = defaultdict(list)
    indeg = defaultdict(int)
    for d in deps:
        if d["type"] == "hard":
            succ[d["depends_on"]].append(d["task_id"])
            indeg[d["task_id"]] += 1
    # 简单：按 task 列表顺序找包含 hard 依赖的链
    critical_path = []
    visited = set()
    for t in tasks:
        if t["id"] in visited: continue
        if any(d["task_id"] == t["id"] and d["type"] == "hard" for d in deps):
            chain = [t["id"]]
            cur_id = t["id"]
            # 前缀
            for d in deps:
                if d["task_id"] == cur_id and d["type"] == "hard":
                    pass
            critical_path.append(t["id"])
            visited.add(t["id"])

    # 下个卡点：未完成且有 hard 依赖未满足的任务
    done_set = {t["id"] for t in tasks if t["status"] == "done"}
    next_blocker = None
    for t in tasks:
        if t["status"] == "done": continue
        for d in deps:
            if d["task_id"] == t["id"] and d["type"] == "hard" and d["depends_on"] not in done_set:
                next_blocker = {
                    "task_id": t["id"], "task_title": t["title"],
                    "blocked_by": d["depends_on"],
                }
                break
        if next_blocker: break

    return {
        "phases": phases,
        "critical_path_count": len(critical_path),
        "next_blocker": next_blocker,
    }


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
