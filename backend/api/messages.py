"""
api/messages.py — 沟通消息

学生/家长 ↔ 顾问 双向。放宽 Gobob 原 student↔mentor 硬编码白名单，
允许 student/parent ↔ advisor/owner 之间对话。
conversation_id = 两个 member_id 排序后哈希。
"""

import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor
from core.id_gen import new_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/messages", tags=["messages"])

_STUDENT_SIDE = {auth.ROLE_STUDENT, auth.ROLE_PARENT}
_STAFF_SIDE = {auth.ROLE_OWNER, auth.ROLE_ADVISOR}


def _conv_id(a: str, b: str) -> str:
    pair = "|".join(sorted([a, b]))
    return hashlib.sha256(pair.encode()).hexdigest()[:32]


def _row(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _check_pair(user: dict, other_member_id: str, org_id: str) -> dict:
    """校验对话双方法：学生侧 ↔ 员工侧。返回对方 member 记录。"""
    with db_cursor() as cur:
        cur.execute("SELECT id, role, name FROM members WHERE id=%s AND org_id=%s",
                    (other_member_id, org_id))
        other = cur.fetchone()
    if not other:
        raise HTTPException(404, "对方不存在")
    my_role = user["role"]
    other_role = other["role"]
    ok = (my_role in _STUDENT_SIDE and other_role in _STAFF_SIDE) or \
         (my_role in _STAFF_SIDE and other_role in _STUDENT_SIDE) or \
         (my_role in _STAFF_SIDE and other_role in _STAFF_SIDE)  # 员工之间也可
    if not ok:
        raise HTTPException(403, "仅支持学生/家长与机构员工之间沟通")
    return other


class SendReq(BaseModel):
    to_member_id: str
    content: str = Field(..., min_length=1)


@router.post("")
def send(req: SendReq, user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id)):
    me = user.get("member_id")
    if not me:
        raise HTTPException(403, "无成员身份")
    other = _check_pair(user, req.to_member_id, org_id)
    cid = _conv_id(me, req.to_member_id)
    mid = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO messages (id, org_id, conversation_id, sender_member_id, receiver_member_id, content)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (mid, org_id, cid, me, req.to_member_id, req.content))
        # 通知接收人
        cur.execute(
            "INSERT INTO notifications (id, org_id, member_id, title, content, type) VALUES (%s,%s,%s,%s,%s,'message')",
            (new_id(), org_id, req.to_member_id, f"新消息 — {user.get('name') or '机构'}", req.content[:100]))
    return {"message_id": mid, "conversation_id": cid}


@router.get("/conversations")
def conversations(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id)):
    """我的会话列表（最近一条 + 未读数 + 对方姓名）。"""
    me = user.get("member_id")
    with db_cursor() as cur:
        cur.execute(
            """SELECT conversation_id,
                 MAX(created_at) AS last_at,
                 SUM(CASE WHEN receiver_member_id=%s AND is_read=0 THEN 1 ELSE 0 END) AS unread,
                 SUBSTRING_INDEX(GROUP_CONCAT(content ORDER BY created_at DESC), ',', 1) AS last_msg,
                 SUBSTRING_INDEX(GROUP_CONCAT(CASE WHEN sender_member_id!=%s THEN sender_member_id ELSE receiver_member_id END ORDER BY created_at DESC), ',', 1) AS other_id
               FROM messages WHERE org_id=%s AND (sender_member_id=%s OR receiver_member_id=%s)
               GROUP BY conversation_id ORDER BY last_at DESC LIMIT 100""",
            (me, me, org_id, me, me))
        convs = cur.fetchall()
        for c in convs:
            cur.execute("SELECT name FROM members WHERE id=%s", (c["other_id"],))
            r = cur.fetchone()
            c["other_name"] = r["name"] if r else "?"
    return {"items": [_row(c) for c in convs]}


@router.get("/with/{other_member_id}")
def conversation_with(other_member_id: str, user: dict = Depends(auth.get_current_user),
                      org_id: str = Depends(get_org_id), limit: int = Query(100, le=200)):
    me = user.get("member_id")
    other = _check_pair(user, other_member_id, org_id)
    cid = _conv_id(me, other_member_id)
    with db_cursor() as cur:
        cur.execute(
            """SELECT m.*, s.name AS sender_name FROM messages m
               LEFT JOIN members s ON s.id=m.sender_member_id
               WHERE m.conversation_id=%s AND m.org_id=%s ORDER BY m.created_at DESC LIMIT %s""",
            (cid, org_id, limit))
        msgs = [_row(r) for r in cur.fetchall()]
        # 标记对方发来的为已读
        cur.execute(
            "UPDATE messages SET is_read=1 WHERE conversation_id=%s AND receiver_member_id=%s AND is_read=0",
            (cid, me))
    msgs.reverse()
    return {"conversation_id": cid, "other": _row(other), "messages": msgs}
