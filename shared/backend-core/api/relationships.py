"""
api/relationships.py — 家长/学生多对多关系 — Phase 5

现状：member_relationships(from_member_id, to_member_id, rel_type) 表已存在，
需补 API 让 owner/advisor 维护关系（之前没路由）。
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor
from core.id_gen import new_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/relationships", tags=["relationships"])

ALLOWED_RELS = {"father", "mother", "guardian", "spouse", "self"}


class RelReq(BaseModel):
    from_member_id: str
    to_member_id: str
    rel_type: str = Field(..., description="father/mother/guardian/spouse/self")


def _row(r) -> dict:
    d = dict(r)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return d


@router.post("/")
def add_rel(req: RelReq, user: dict = Depends(auth.require_staff),
            org_id: str = Depends(get_org_id)):
    if req.rel_type not in ALLOWED_RELS:
        raise HTTPException(400, f"rel_type 必须是 {ALLOWED_RELS}")
    if req.from_member_id == req.to_member_id:
        raise HTTPException(400, "不能关联自己")
    with db_cursor() as cur:
        for mid in (req.from_member_id, req.to_member_id):
            cur.execute("SELECT id, role, name FROM members WHERE id=%s AND org_id=%s", (mid, org_id))
            row = cur.fetchone()
            if not row: raise HTTPException(404, f"成员 {mid} 不存在")
            if mid == req.from_member_id and row["role"] not in ("parent", "spouse"):
                raise HTTPException(400, f"{row['name']} 角色是 {row['role']}，不能作为'关联方'")
        cur.execute(
            """INSERT INTO member_relationships (id, org_id, from_member_id, to_member_id, rel_type)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE rel_type=VALUES(rel_type)""",
            (new_id(), org_id, req.from_member_id, req.to_member_id, req.rel_type))
    return {"ok": True}


@router.get("/student/{student_id}/parents")
def student_parents(student_id: str, user: dict = Depends(auth.get_current_user),
                    org_id: str = Depends(get_org_id)):
    """一个学生关联的所有家长/监护人"""
    with db_cursor() as cur:
        cur.execute(
            """SELECT m.id, m.name, m.phone, m.wechat, m.email, r.rel_type, r.created_at
               FROM member_relationships r JOIN members m ON m.id=r.from_member_id
               WHERE r.to_member_id=%s AND r.org_id=%s AND m.role IN ('parent','spouse')""",
            (student_id, org_id))
        rows = [_row(r) for r in cur.fetchall()]
    return {"parents": rows}


@router.get("/parent/{parent_id}/students")
def parent_students(parent_id: str, user: dict = Depends(auth.get_current_user),
                    org_id: str = Depends(get_org_id)):
    """一个家长关联的所有学生（家长顶部切换用）"""
    with db_cursor() as cur:
        cur.execute(
            """SELECT m.id, m.name, m.phone, r.rel_type, r.created_at
               FROM member_relationships r JOIN members m ON m.id=r.to_member_id
               WHERE r.from_member_id=%s AND r.org_id=%s AND m.role='student'""",
            (parent_id, org_id))
        rows = [_row(r) for r in cur.fetchall()]
    return {"students": rows}


@router.delete("/{rel_id}")
def del_rel(rel_id: str, user: dict = Depends(auth.require_owner),
            org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("DELETE FROM member_relationships WHERE id=%s AND org_id=%s", (rel_id, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "关系不存在")
    return {"ok": True}
