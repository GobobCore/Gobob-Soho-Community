"""
api/students.py — 学生档案与列表

学生列表（机构端：老板全量/顾问看自己负责的）、档案聚合（user_profile/academic_profile/study_intent）。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core import auth
from core.database import db_cursor
from core.id_gen import new_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/students", tags=["students"])


def _row(row) -> dict:
    d = dict(row)
    for k in ("target_countries", "target_degrees", "target_majors", "language_scores", "extra"):
        if d.get(k) and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif hasattr(v, "isoformat") and not isinstance(v, str):
            d[k] = v.isoformat()
    return d


# ── 学生列表（机构端）────────────────────────────────────────────

@router.get("")
def list_students(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id),
                  q: str | None = None, page: int = Query(1, ge=1),
                  page_size: int = Query(50, ge=1, le=200)):
    """学生列表。老板看全部；顾问只看自己被分配到的（任一环节）。"""
    params = [org_id]
    join = ""
    where = ["m.org_id=%s", "m.role='student'"]
    if user["role"] == auth.ROLE_ADVISOR:
        join = "JOIN service_assignments sa ON sa.student_member_id=m.id AND sa.advisor_member_id=%s AND sa.status='active'"
        params.append(user.get("member_id"))
    if q:
        where.append("m.name LIKE %s")
        params.append(f"%{q}%")
    sql_where = " AND ".join(where)
    offset = (page - 1) * page_size
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(DISTINCT m.id) AS c FROM members m {join} WHERE {sql_where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT DISTINCT m.id, m.name, m.phone, m.wechat, m.is_virtual, m.created_at,
                  (SELECT GROUP_CONCAT(DISTINCT adv.name) FROM service_assignments sa2
                    LEFT JOIN members adv ON adv.id=sa2.advisor_member_id
                    WHERE sa2.student_member_id=m.id AND sa2.status='active') AS advisors
                FROM members m {join}
                WHERE {sql_where} ORDER BY m.created_at DESC LIMIT %s OFFSET %s""",
            params + [page_size, offset])
        rows = [_row(r) for r in cur.fetchall()]
    return {"total": total, "items": rows}


# ── 学生详情聚合 ──────────────────────────────────────────────────

@router.get("/{member_id}")
def student_detail(member_id: str, user: dict = Depends(auth.get_current_user),
                   org_id: str = Depends(get_org_id)):
    # 权限：员工任意看；学生/家长只能看自己/孩子
    if user["role"] in (auth.ROLE_STUDENT, auth.ROLE_PARENT):
        if user.get("member_id") != member_id:
            with db_cursor() as cur:
                cur.execute("SELECT 1 FROM member_relationships WHERE from_member_id=%s AND to_member_id=%s AND org_id=%s",
                            (user.get("member_id"), member_id, org_id))
                if not cur.fetchone():
                    raise HTTPException(403, "无权查看")
    with db_cursor() as cur:
        cur.execute("SELECT id, name, phone, wechat, email, is_virtual, created_at FROM members WHERE id=%s AND org_id=%s AND role='student'",
                    (member_id, org_id))
        stu = cur.fetchone()
        if not stu:
            raise HTTPException(404, "学生不存在")
        for table in ("user_profile", "academic_profile", "study_intent"):
            cur.execute(f"SELECT * FROM {table} WHERE member_id=%s", (member_id,))
            row = cur.fetchone()
            stu[table] = _row(row) if row else None
        # 当前负责老师（按环节）
        cur.execute(
            """SELECT sa.id, sa.phase, sa.started_at, adv.id AS advisor_id, adv.name AS advisor_name
               FROM service_assignments sa LEFT JOIN members adv ON adv.id=sa.advisor_member_id
               WHERE sa.student_member_id=%s AND sa.status='active'""", (member_id,))
        stu["advisors"] = [_row(r) for r in cur.fetchall()]
        # 评估快照
        cur.execute("SELECT id, created_at FROM assessments WHERE member_id=%s ORDER BY created_at DESC LIMIT 5",
                    (member_id,))
        stu["assessments"] = [_row(r) for r in cur.fetchall()]
    return _row(stu)


# ── 档案读写 ──────────────────────────────────────────────────────

class ProfileReq(BaseModel):
    real_name: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    id_number: str | None = None
    address: str | None = None


def _can_edit_student(member_id: str, user: dict, org_id: str) -> bool:
    if user["role"] in (auth.ROLE_OWNER, auth.ROLE_ADVISOR):
        return True
    return user.get("member_id") == member_id


@router.put("/{member_id}/profile")
def put_profile(member_id: str, req: ProfileReq, user: dict = Depends(auth.get_current_user),
                org_id: str = Depends(get_org_id)):
    if not _can_edit_student(member_id, user, org_id):
        raise HTTPException(403, "无权编辑")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM user_profile WHERE member_id=%s", (member_id,))
        existing = cur.fetchone()
        data = {k: v for k, v in req.model_dump().items() if v is not None}
        if existing:
            if data:
                sets = ", ".join(f"{k}=%s" for k in data)
                cur.execute(f"UPDATE user_profile SET {sets} WHERE member_id=%s",
                            list(data.values()) + [member_id])
        else:
            cur.execute(
                "INSERT INTO user_profile (id, org_id, member_id, real_name, gender, birth_date, id_number, address) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (new_id(), org_id, member_id, req.real_name, req.gender, req.birth_date, req.id_number, req.address))
    return {"ok": True}


class AcademicReq(BaseModel):
    current_school: str | None = None
    grade: str | None = None
    gpa: float | None = None
    gpa_scale: str | None = None
    language_scores: list | None = None


@router.put("/{member_id}/academic")
def put_academic(member_id: str, req: AcademicReq, user: dict = Depends(auth.get_current_user),
                 org_id: str = Depends(get_org_id)):
    if not _can_edit_student(member_id, user, org_id):
        raise HTTPException(403, "无权编辑")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM academic_profile WHERE member_id=%s", (member_id,))
        existing = cur.fetchone()
        ls = json.dumps(req.language_scores) if req.language_scores is not None else None
        if existing:
            cur.execute(
                """UPDATE academic_profile SET current_school=COALESCE(%s,current_school),
                   grade=COALESCE(%s,grade), gpa=COALESCE(%s,gpa), gpa_scale=COALESCE(%s,gpa_scale),
                   language_scores=COALESCE(%s,language_scores) WHERE member_id=%s""",
                (req.current_school, req.grade, req.gpa, req.gpa_scale, ls, member_id))
        else:
            cur.execute(
                "INSERT INTO academic_profile (id, org_id, member_id, current_school, grade, gpa, gpa_scale, language_scores) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (new_id(), org_id, member_id, req.current_school, req.grade, req.gpa, req.gpa_scale, ls))
    return {"ok": True}


class IntentReq(BaseModel):
    target_countries: list | None = None
    target_degrees: list | None = None
    target_majors: list | None = None
    target_year: int | None = None
    budget_min: float | None = None
    budget_max: float | None = None


@router.put("/{member_id}/intent")
def put_intent(member_id: str, req: IntentReq, user: dict = Depends(auth.get_current_user),
               org_id: str = Depends(get_org_id)):
    if not _can_edit_student(member_id, user, org_id):
        raise HTTPException(403, "无权编辑")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM study_intent WHERE member_id=%s", (member_id,))
        existing = cur.fetchone()
        vals = (json.dumps(req.target_countries) if req.target_countries is not None else None,
                json.dumps(req.target_degrees) if req.target_degrees is not None else None,
                json.dumps(req.target_majors) if req.target_majors is not None else None,
                req.target_year, req.budget_min, req.budget_max)
        if existing:
            cur.execute(
                """UPDATE study_intent SET target_countries=COALESCE(%s,target_countries),
                   target_degrees=COALESCE(%s,target_degrees), target_majors=COALESCE(%s,target_majors),
                   target_year=COALESCE(%s,target_year), budget_min=COALESCE(%s,budget_min),
                   budget_max=COALESCE(%s,budget_max) WHERE member_id=%s""",
                vals + (member_id,))
        else:
            cur.execute(
                "INSERT INTO study_intent (id, org_id, member_id, target_countries, target_degrees, target_majors, target_year, budget_min, budget_max) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (new_id(), org_id, member_id) + vals)
    return {"ok": True}
