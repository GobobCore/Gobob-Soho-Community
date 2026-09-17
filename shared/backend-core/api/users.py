"""
api/users.py — 用户管理 (owner 权限) — SaaS 多机构 + 社区版通用
================================================================

支持 4 种角色 (owner/advisor/student/parent):
  - POST   /api/users              — 创建 (含免费配额校验)
  - GET    /api/users              — 列表
  - GET    /api/users/{member_id}  — 详情
  - PUT    /api/users/{member_id}  — 修改 (name/phone/email/title/specialty/is_active)
  - DELETE /api/users/{member_id}  — 停用 (is_active=0)
  - POST   /api/users/{member_id}/reset-password  — owner 重置密码
  - GET    /api/users/quotas       — 当前配额 (owner=1, advisor=2 免费)

免费配额 (SaaS plan_status='free'):
  - owner ≤ 1 个 (管理员本身可作为业务用户参与协作)
  - advisor ≤ 2 个
  - student/parent 单独由机构内部决定, 无硬性限制
  - 创建超出 → 422 QUOTA_EXCEEDED, body 含 purchase_url

付费 (seats_paid > 0) — 不限人数 (按 seats_paid 计数).

替代旧 staff.py (保留兼容, staff.py 接口仍可用).
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/users", tags=["users"])

ALL_ROLES = ("owner", "advisor", "student", "parent")

# 免费配额常量
FREE_OWNER_LIMIT = 1
FREE_ADVISOR_LIMIT = 2


def _row(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    d.pop("password_hash", None)
    return d


# ── 配额检查 helper ─────────────────────────────────────────────

def _check_quota(cur, org_id: str, role: str) -> None:
    """创建用户前调用. 超免费配额 → 422."""
    # 只对 owner/advisor 限制. student/parent 由机构内部管理
    if role not in ("owner", "advisor"):
        return
    cur.execute("SELECT plan_status, seats_paid FROM orgs WHERE id=%s", (org_id,))
    org = cur.fetchone()
    if not org:
        raise HTTPException(404, "机构不存在")
    # 已付费 — 不限
    if org["plan_status"] != "free" and (org["seats_paid"] or 0) > 0:
        return
    # 免费版 — 检查 owner/advisor 数
    cur.execute(
        "SELECT COUNT(*) AS c FROM members WHERE org_id=%s AND role=%s AND is_active=1 AND is_virtual=0",
        (org_id, role),
    )
    cur_count = cur.fetchone()["c"]
    limit = FREE_OWNER_LIMIT if role == "owner" else FREE_ADVISOR_LIMIT
    if cur_count >= limit:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "QUOTA_EXCEEDED",
                "message": f"免费版最多 {limit} 个 {role}, 超出需购买用户席位 (¥1000/席位/年)",
                "current": cur_count,
                "limit": limit,
                "purchase_url": "/buy-quota?type=seats",
            },
        )


# ── 列表 + 配额查询 ──────────────────────────────────────────────

@router.get("/quotas")
def get_quotas(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id)):
    """当前机构用户配额 (任何登录用户可读)."""
    with db_cursor() as cur:
        cur.execute("SELECT plan_status, seats_paid, paid_until FROM orgs WHERE id=%s", (org_id,))
        org = cur.fetchone()
        cur.execute(
            """SELECT role, COUNT(*) AS c FROM members
               WHERE org_id=%s AND is_active=1 AND is_virtual=0
               GROUP BY role""",
            (org_id,),
        )
        by_role = {r["role"]: r["c"] for r in cur.fetchall()}
    plan = org["plan_status"] if org else "free"
    paid_seats = (org["seats_paid"] or 0) if org else 0
    return {
        "plan_status": plan,
        "seats_paid": paid_seats,
        "paid_until": org["paid_until"].isoformat() if org and org["paid_until"] else None,
        "counts": {
            "owner": by_role.get("owner", 0),
            "advisor": by_role.get("advisor", 0),
            "student": by_role.get("student", 0),
            "parent": by_role.get("parent", 0),
            "total": sum(by_role.values()),
        },
        "free_limits": {
            "owner": FREE_OWNER_LIMIT,
            "advisor": FREE_ADVISOR_LIMIT,
            "student": None,  # 公开版不限制学生/家长
            "parent": None,
        },
        "is_free_blocked": plan == "free" and (
            by_role.get("owner", 0) >= FREE_OWNER_LIMIT
            or by_role.get("advisor", 0) >= FREE_ADVISOR_LIMIT
        ),
    }


@router.get("")
def list_users(
    role: str | None = Query(None, description="过滤角色 owner/advisor/student/parent"),
    user: dict = Depends(auth.require_owner),
    org_id: str = Depends(get_org_id),
):
    """所有用户列表 (含 student/parent, 不只是员工)."""
    role_filter = ""
    params = [org_id]
    if role:
        if role not in ALL_ROLES:
            raise HTTPException(400, f"role 必须是 {ALL_ROLES}")
        role_filter = " AND m.role=%s"
        params.append(role)
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT m.id, m.account_id, m.name, m.role, m.title, m.specialty, m.phone, m.email,
                       m.wechat, m.is_active, m.is_virtual, m.created_at,
                       a.username
                FROM members m
                LEFT JOIN accounts a ON a.id = m.account_id
                WHERE m.org_id=%s {role_filter}
                ORDER BY FIELD(m.role,'owner','advisor','student','parent'), m.created_at""",
            params,
        )
        rows = [_row(r) for r in cur.fetchall()]
    return {"items": rows}


@router.get("/{member_id}")
def get_user(member_id: str, user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute(
            """SELECT m.*, a.username
               FROM members m LEFT JOIN accounts a ON a.id = m.account_id
               WHERE m.id=%s AND m.org_id=%s""",
            (member_id, org_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "用户不存在")
    return _row(row)


# ── 创建 ────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    username: str | None = Field(None, min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$",
                                 description="登录用户名 (advisor/owner 必填, student/parent 可选)")
    password: str | None = Field(None, min_length=6, max_length=64,
                                  description="密码 (advisor/owner 必填, student/parent 可选 — 用 account_id 给 student/parent 关联)")
    role: Literal["owner", "advisor", "student", "parent"]
    title: str | None = Field(None, max_length=100, description="职位/角色描述 (advisor)")
    specialty: str | None = Field(None, max_length=255, description="专长 (advisor)")
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    wechat: str | None = Field(None, max_length=100)
    is_virtual: bool = Field(False, description="True = 无登录账号 (代管档案)")


@router.post("")
def create_user(req: UserCreate, user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    # owner 创建其他 owner 允许吗? — 允许 (multi-owner), 但需要 seats
    # advisor/student/parent 创建 — 走配额校验
    with db_transaction() as cur:
        _check_quota(cur, org_id, req.role)

        account_id = None
        member_id = new_id()

        # advisor/owner 必须有账号 (用于登录)
        is_login_role = req.role in ("owner", "advisor")
        if is_login_role:
            if not req.username or not req.password:
                raise HTTPException(400, f"{req.role} 必须设置 username + password 才能登录")
            cur.execute(
                "SELECT id FROM accounts WHERE org_id=%s AND username=%s",
                (org_id, req.username),
            )
            if cur.fetchone():
                raise HTTPException(409, f"用户名 '{req.username}' 已存在")
            account_id = new_id()
            cur.execute(
                "INSERT INTO accounts (id, org_id, username, password_hash, phone, email) VALUES (%s,%s,%s,%s,%s,%s)",
                (account_id, org_id, req.username, auth.hash_password(req.password),
                 req.phone, req.email),
            )
        else:
            # student/parent 可选 username (代建无账号档案)
            if req.username:
                cur.execute(
                    "SELECT id FROM accounts WHERE org_id=%s AND username=%s",
                    (org_id, req.username),
                )
                if cur.fetchone():
                    raise HTTPException(409, f"用户名 '{req.username}' 已存在")
                account_id = new_id()
                cur.execute(
                    "INSERT INTO accounts (id, org_id, username, password_hash, phone, email) VALUES (%s,%s,%s,%s,%s,%s)",
                    (account_id, org_id, req.username,
                     auth.hash_password(req.password) if req.password else "",
                     req.phone, req.email),
                )

        cur.execute(
            """INSERT INTO members (id, org_id, account_id, name, role, is_virtual, title, specialty,
                                     phone, email, wechat)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (member_id, org_id, account_id, req.name, req.role,
             1 if req.is_virtual or not account_id else 0,
             req.title, req.specialty, req.phone, req.email, req.wechat),
        )
    return {"member_id": member_id, "account_id": account_id}


# ── 修改 ────────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    title: str | None = Field(None, max_length=100)
    specialty: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    wechat: str | None = Field(None, max_length=100)
    is_active: bool | None = None


@router.put("/{member_id}")
def update_user(member_id: str, req: UserUpdate, user: dict = Depends(auth.require_owner),
               org_id: str = Depends(get_org_id)):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        return {"ok": True}
    sets = ", ".join(f"{k}=%s" for k in data)
    with db_cursor() as cur:
        cur.execute(
            f"UPDATE members SET {sets} WHERE id=%s AND org_id=%s",
            list(data.values()) + [member_id, org_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "用户不存在")
    return {"ok": True}


# ── 停用 ────────────────────────────────────────────────────────

@router.delete("/{member_id}")
def disable_user(member_id: str, user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    # 不能停用最后一个 owner
    with db_cursor() as cur:
        cur.execute("SELECT role FROM members WHERE id=%s AND org_id=%s", (member_id, org_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        if row["role"] == "owner":
            cur.execute("SELECT COUNT(*) AS c FROM members WHERE org_id=%s AND role='owner' AND is_active=1 AND id!=%s",
                        (org_id, member_id))
            if cur.fetchone()["c"] == 0:
                raise HTTPException(400, "不能停用最后一个 owner")
        cur.execute("UPDATE members SET is_active=0 WHERE id=%s AND org_id=%s", (member_id, org_id))
    return {"ok": True}


# ── 重置密码 (owner 操作) ───────────────────────────────────────

class ResetPwdReq(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=64)


@router.post("/{member_id}/reset-password")
def reset_password(member_id: str, req: ResetPwdReq, user: dict = Depends(auth.require_owner),
                   org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("SELECT account_id FROM members WHERE id=%s AND org_id=%s", (member_id, org_id))
        row = cur.fetchone()
        if not row or not row["account_id"]:
            raise HTTPException(404, "该用户无登录账号")
        cur.execute("UPDATE accounts SET password_hash=%s WHERE id=%s",
                    (auth.hash_password(req.new_password), row["account_id"]))
    return {"ok": True}