"""
api/dashboard.py — 管理驾驶舱（老板/主管视图）

老板：全机构学生进度、各老师负载、漏斗、本月签约。
顾问：我的线索、我的学生、今日待办。

核心聚合：每个学生 → 负责老师、当前阶段、已完成/进行中/待办任务数。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from core import auth
from core.database import db_cursor
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _row(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


@router.get("/overview")
def overview(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    is_owner = user["role"] == auth.ROLE_OWNER
    mid = user.get("member_id")
    with db_cursor() as cur:
        # 线索漏斗
        lead_where = "org_id=%s AND is_recycled=0" + ("" if is_owner else " AND assigned_advisor_id=%s")
        lead_params = [org_id] + ([] if is_owner else [mid])
        cur.execute(f"SELECT status, COUNT(*) AS c FROM leads WHERE {lead_where} GROUP BY status", lead_params)
        lead_funnel = {r["status"]: r["c"] for r in cur.fetchall()}

        # 学生数
        stu_where = "m.org_id=%s AND m.role='student'"
        stu_params = [org_id]
        join = ""
        if not is_owner:
            join = "JOIN service_assignments sa ON sa.student_member_id=m.id AND sa.advisor_member_id=%s AND sa.status='active'"
            stu_params.append(mid)
        cur.execute(f"SELECT COUNT(DISTINCT m.id) AS c FROM members m {join} WHERE {stu_where}", stu_params)
        student_count = cur.fetchone()["c"]

        # 本月签约
        cur.execute(
            """SELECT COUNT(*) AS c, COALESCE(SUM(total_amount),0) AS amt FROM contracts
               WHERE org_id=%s AND DATE_FORMAT(created_at,'%%Y-%%m')=DATE_FORMAT(NOW(),'%%Y-%%m')""",
            (org_id,))
        month_contract = cur.fetchone()

        # 老师负载（owner 看全部；顾问只看自己）
        load_where = "m.org_id=%s AND m.role='advisor' AND m.is_active=1"
        load_params = [org_id]
        if not is_owner:
            load_where += " AND m.id=%s"
            load_params.append(mid)
        cur.execute(
            f"""SELECT m.id, m.name,
                  (SELECT COUNT(DISTINCT sa.student_member_id) FROM service_assignments sa
                    WHERE sa.advisor_member_id=m.id AND sa.status='active') AS active_students,
                  (SELECT COUNT(*) FROM leads l WHERE l.assigned_advisor_id=m.id AND l.is_recycled=0 AND l.status NOT IN ('converted','lost')) AS open_leads
                FROM members m WHERE {load_where} ORDER BY active_students DESC""",
            load_params)
        advisor_load = [_row(r) for r in cur.fetchall()]
    return {
        "lead_funnel": lead_funnel,
        "student_count": student_count,
        "month_contract_count": month_contract["c"],
        "month_contract_amount": float(month_contract["amt"] or 0),
        "advisor_load": advisor_load,
        "is_owner": is_owner,
    }


@router.get("/students-progress")
def students_progress(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id),
                      page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    """学生进度总览：每个学生 → 负责老师（按环节）、任务 done/doing/next、最近动态。"""
    is_owner = user["role"] == auth.ROLE_OWNER
    params = [org_id]
    join = ""
    where = ["m.org_id=%s", "m.role='student'"]
    if not is_owner:
        join = "JOIN service_assignments sa ON sa.student_member_id=m.id AND sa.advisor_member_id=%s AND sa.status='active'"
        params.append(user.get("member_id"))
    sql_where = " AND ".join(where)
    offset = (page - 1) * page_size
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(DISTINCT m.id) AS c FROM members m {join} WHERE {sql_where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT m.id, MIN(m.name) AS name FROM (
                  SELECT DISTINCT m.id, m.name, m.created_at FROM members m {join} WHERE {sql_where}
                ) m GROUP BY m.id ORDER BY MIN(m.created_at) DESC LIMIT %s OFFSET %s""",
            params + [page_size, offset])
        students = cur.fetchall()

        out = []
        for s in students:
            sid = s["id"]
            # 负责老师（按环节）
            cur.execute(
                """SELECT sa.phase, adv.name FROM service_assignments sa
                   LEFT JOIN members adv ON adv.id=sa.advisor_member_id
                   WHERE sa.student_member_id=%s AND sa.status='active'""", (sid,))
            advisors = {r["phase"]: r["name"] for r in cur.fetchall()}
            # 任务统计
            cur.execute(
                """SELECT
                     SUM(status='done') AS done,
                     SUM(status='in_progress') AS doing,
                     SUM(status='pending') AS todo
                   FROM tasks WHERE member_id=%s""", (sid,))
            t = cur.fetchone()
            # 最近完成的任务
            cur.execute(
                "SELECT title, completed_at FROM tasks WHERE member_id=%s AND status='done' ORDER BY completed_at DESC LIMIT 3",
                (sid,))
            recent_done = [_row(r) for r in cur.fetchall()]
            # 下一个待办
            cur.execute(
                "SELECT title, due_date FROM tasks WHERE member_id=%s AND status IN ('pending','in_progress') ORDER BY due_date IS NULL, due_date LIMIT 3",
                (sid,))
            next_tasks = [_row(r) for r in cur.fetchall()]
            # 当前阶段（最近 active milestone）
            cur.execute(
                "SELECT title, phase, status FROM milestones WHERE member_id=%s AND status='in_progress' ORDER BY sort_order LIMIT 1",
                (sid,))
            current = cur.fetchone()
            out.append({
                "student_id": sid,
                "student_name": s["name"],
                "advisors": advisors,
                "current_stage": _row(current) if current else None,
                "task_stats": {"done": int(t["done"] or 0), "doing": int(t["doing"] or 0), "todo": int(t["todo"] or 0)},
                "recent_done": recent_done,
                "next_tasks": next_tasks,
            })
    return {"total": total, "items": out}
