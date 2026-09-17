"""
api/auth_router.py — 登录 / 注册 / 当前用户

学生 / 家长账号由机构在服务平台内创建（非公开注册），
获客门户的留资进 leads（不建账号）。
机构自助注册公开：POST /api/register — 创建一个新 org + owner 账号 + 默认 pipeline.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor
from core.id_gen import new_id

log = logging.getLogger("auth")
router = APIRouter(prefix="/api", tags=["auth"])


class LoginReq(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/login")
def login(req: LoginReq):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, org_id FROM accounts WHERE username=%s LIMIT 1",
            (req.username,),
        )
        acc = cur.fetchone()
        if not acc or not auth.verify_password(req.password, acc["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        cur.execute(
            "SELECT id, role, name FROM members WHERE account_id=%s LIMIT 1",
            (acc["id"],),
        )
        mem = cur.fetchone()
    role = mem["role"] if mem else auth.ROLE_STUDENT
    token = auth.create_token(acc["id"], acc["username"], role, acc["org_id"])
    return {
        "token": token,
        "user": {
            "id": acc["id"],
            "username": acc["username"],
            "name": mem["name"] if mem else acc["username"],
            "role": role,
            "org_id": acc["org_id"],
            "member_id": mem["id"] if mem else None,
            "is_admin": role == auth.ROLE_OWNER,
        },
    }


@router.get("/me")
def me(user: dict = Depends(auth.get_current_user)):
    return {
        "id": user["sub"],
        "username": user["username"],
        "name": user.get("name"),
        "role": user["role"],
        "org_id": user["org_id"],
        "member_id": user.get("member_id"),
        "is_admin": user.get("is_admin"),
    }


# ── 机构自助注册 (公开) ─────────────────────────────────────────

class RegisterReq(BaseModel):
    org_name: str = Field(..., min_length=2, max_length=100, description="机构名 (例: 我的留学工作室)")
    org_slug: str | None = Field(None, min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$",
                                  description="机构 slug (SaaS 多机构用, 例: demo-studio. 开源版可空)")
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$", description="登录用户名")
    password: str = Field(..., min_length=8, max_length=64, description="密码 (≥8 位)")
    owner_name: str = Field(..., min_length=1, max_length=50, description="老板/主管姓名")
    contact_phone: str | None = Field(None, max_length=50)
    contact_email: str | None = Field(None, max_length=200)
    # R-Refactor 2026-09-17: SaaS 设置页 — 注册可选填机构信息 (description/address/website/logo_url)
    description: str | None = Field(None, max_length=2000, description="机构简介")
    address: str | None = Field(None, max_length=500, description="商务地址")
    website: str | None = Field(None, max_length=500, description="官方网站 URL")
    logo_url: str | None = Field(None, max_length=500, description="机构 logo URL")


@router.post("/register")
def register_org(req: RegisterReq):
    """公开: 创建新机构 + 老板账号 + owner member + 默认 pipeline 阶段绑定.

    调用后立即登录返回 token, 前端可直接跳转到 soho-app.
    """
    with db_cursor() as cur:
        # 用户名唯一性
        cur.execute("SELECT id FROM accounts WHERE username=%s LIMIT 1", (req.username,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="用户名已被占用，请换一个")
        # slug 唯一性 (SaaS 多机构用)
        if req.org_slug:
            cur.execute("SELECT id FROM orgs WHERE slug=%s LIMIT 1", (req.org_slug,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=f"机构 slug '{req.org_slug}' 已被占用，请换一个")
        # 机构名宽松去重 (同名不阻止, 但会加备注, 机构名本身允许重名)
        # 创建
        org_id = new_id()
        cur.execute(
            """INSERT INTO orgs (id, name, slug, address, email, website, logo_url, description,
                                  contact_phone, contact_email, contact_name)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (org_id, req.org_name, req.org_slug, req.address, req.contact_email,
             req.website, req.logo_url, req.description,
             req.contact_phone, req.contact_email, req.owner_name),
        )
        acc_id = new_id()
        cur.execute(
            "INSERT INTO accounts (id, username, password_hash, org_id) VALUES (%s, %s, %s, %s)",
            (acc_id, req.username, auth.hash_password(req.password), org_id),
        )
        member_id = new_id()
        cur.execute(
            "INSERT INTO members (id, account_id, org_id, name, role) VALUES (%s, %s, %s, %s, %s)",
            (member_id, acc_id, org_id, req.owner_name, auth.ROLE_OWNER),
        )
        # 把 default 的 pipeline 阶段绑过来
        cur.execute(
            "INSERT INTO lead_pipeline_stages (stage_id, org_id, name, sort_order, is_start, is_won, is_lost, max_days) "
            "SELECT stage_id, %s, name, sort_order, is_start, is_won, is_lost, max_days "
            "FROM lead_pipeline_stages WHERE org_id='default'",
            (org_id,),
        )
        stages_copied = cur.rowcount
        # 复制 pipeline stages 到新机构 (R-Fix 2026-09-16 v0.18.0: PK 已改 (stage_id, org_id) 联合, 可安全复制)
        # 从任一已有机构复制 (优先 plan_status=paid, 其次任一非 suspended)
        cur.execute(
            """SELECT org_id FROM lead_pipeline_stages s
               JOIN orgs o ON o.id = s.org_id
               WHERE o.plan_status != 'suspended' AND s.org_id != %s
               GROUP BY s.org_id
               ORDER BY (o.plan_status = 'paid') DESC, o.created_at ASC
               LIMIT 1""",
            (org_id,),
        )
        tpl = cur.fetchone()
        if tpl:
            cur.execute(
                "INSERT INTO lead_pipeline_stages (stage_id, org_id, name, sort_order, is_start, is_won, is_lost, max_days) "
                "SELECT stage_id, %s, name, sort_order, is_start, is_won, is_lost, max_days "
                "FROM lead_pipeline_stages WHERE org_id=%s",
                (org_id, tpl["org_id"]),
            )
            stages_copied = cur.rowcount
        else:
            stages_copied = 0
    log.info("new org registered: id=%s name=%s owner=%s stages=%d (tpl=%s)",
             org_id, req.org_name, req.owner_name, stages_copied, tpl["org_id"] if tpl else "none")
    # 自动登录
    token = auth.create_token(acc_id, req.username, auth.ROLE_OWNER, org_id)
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": acc_id,
            "username": req.username,
            "name": req.owner_name,
            "role": auth.ROLE_OWNER,
            "org_id": org_id,
            "member_id": member_id,
            "is_admin": True,
        },
        "redirect": "/dashboard",
    }
