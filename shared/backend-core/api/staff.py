"""
api/staff.py — 员工管理（owner 权限）

员工（advisor）账号 CRUD、负责学生数、交付绩效。
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/staff", tags=["staff"])


def _row(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    d.pop("password_hash", None)
    return d


class StaffCreate(BaseModel):
    name: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    title: str | None = None
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    role: str = "advisor"  # advisor / owner


@router.post("")
def create_staff(req: StaffCreate, user: dict = Depends(auth.require_owner),
                 org_id: str = Depends(get_org_id)):
    if req.role not in ("advisor", "owner"):
        raise HTTPException(400, "角色只能是 advisor 或 owner")
    with db_transaction() as cur:
        cur.execute("SELECT id FROM accounts WHERE org_id=%s AND username=%s", (org_id, req.username))
        if cur.fetchone():
            raise HTTPException(400, "用户名已存在")
        acc_id = new_id()
        cur.execute(
            "INSERT INTO accounts (id, org_id, username, password_hash, phone, email) VALUES (%s,%s,%s,%s,%s,%s)",
            (acc_id, org_id, req.username, auth.hash_password(req.password), req.phone, req.email))
        mem_id = new_id()
        cur.execute(
            """INSERT INTO members (id, org_id, account_id, name, role, title, specialty, phone, email)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (mem_id, org_id, acc_id, req.name, req.role, req.title, req.specialty, req.phone, req.email))
    return {"member_id": mem_id, "account_id": acc_id}


@router.get("")
def list_staff(user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute(
            """SELECT m.id, m.name, m.role, m.title, m.specialty, m.phone, m.email, m.is_active, m.created_at,
                 (SELECT COUNT(DISTINCT sa.student_member_id) FROM service_assignments sa
                   WHERE sa.advisor_member_id=m.id AND sa.status='active') AS active_students,
                 (SELECT COUNT(*) FROM deliverables d WHERE d.advisor_member_id=m.id
                   AND d.status IN ('in_review','accepted')
                   AND DATE_FORMAT(d.submitted_at,'%%Y-%%m')=DATE_FORMAT(NOW(),'%%Y-%%m')) AS month_deliverables,
                 (SELECT COUNT(*) FROM leads l WHERE l.assigned_advisor_id=m.id AND l.is_recycled=0) AS leads_count
               FROM members m
               WHERE m.org_id=%s AND m.role IN ('owner','advisor')
               ORDER BY m.role='owner' DESC, m.created_at""",
            (org_id,))
        rows = [_row(r) for r in cur.fetchall()]
    return {"items": rows}


class StaffUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    specialty: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool | None = None


@router.put("/{member_id}")
def update_staff(member_id: str, req: StaffUpdate, user: dict = Depends(auth.require_owner),
                 org_id: str = Depends(get_org_id)):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        return {"ok": True}
    sets = ", ".join(f"{k}=%s" for k in data)
    with db_cursor() as cur:
        cur.execute(f"UPDATE members SET {sets} WHERE id=%s AND org_id=%s AND role IN ('owner','advisor')",
                    list(data.values()) + [member_id, org_id])
        if cur.rowcount == 0:
            raise HTTPException(404, "员工不存在")
    return {"ok": True}


class ResetPwdReq(BaseModel):
    new_password: str = Field(..., min_length=6)


@router.post("/{member_id}/reset-password")
def reset_password(member_id: str, req: ResetPwdReq, user: dict = Depends(auth.require_owner),
                   org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("SELECT account_id FROM members WHERE id=%s AND org_id=%s", (member_id, org_id))
        row = cur.fetchone()
        if not row or not row["account_id"]:
            raise HTTPException(404, "员工无登录账号")
        cur.execute("UPDATE accounts SET password_hash=%s WHERE id=%s",
                    (auth.hash_password(req.new_password), row["account_id"]))
    return {"ok": True}
