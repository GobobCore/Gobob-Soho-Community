"""
api/orgs_me.py — 当前机构信息查看 + 修改 (SaaS + 社区版通用)
=============================================================

机构 owner 可改:
  - 机构名 (org_name)
  - 机构简介 (description)
  - 机构地址 (address)
  - 公开联系电话 (phone, 与 owner 个人手机分离)
  - 公开联系邮箱 (email, 与 owner 个人邮箱分离)
  - 官方网站 (website)
  - Logo URL (logo_url, 覆盖 Gobob 默认 logo)

advisor / student / parent: 只读 GET

R-Refactor 2026-09-17 (SaaS 设置页改写):
  - 加 v0.21.0 migration 加 6 列
  - 加 GET/PUT /api/orgs/me
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


class OrgMeUpdateReq(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200, description="机构名")
    description: str | None = Field(None, max_length=2000, description="机构简介")
    address: str | None = Field(None, max_length=500, description="商务地址")
    phone: str | None = Field(None, max_length=50, description="公开联系电话")
    email: str | None = Field(None, max_length=200, description="公开联系邮箱")
    website: str | None = Field(None, max_length=500, description="官方网站 URL")
    logo_url: str | None = Field(None, max_length=500, description="机构 logo URL")


@router.get("/me")
def get_my_org(
    user: dict = Depends(auth.get_current_user),
    org_id: str = Depends(get_org_id),
):
    """任何登录用户可读本机构信息 (用于设置页头部展示 + SaaS 多机构路由)."""
    with db_cursor() as cur:
        cur.execute(
            """SELECT id, name, description, address, phone, email, website, logo_url,
                      gobob_api_key, created_at, updated_at
               FROM orgs WHERE id=%s""",
            (org_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"id": org_id}  # 理论上不存在, 但不抛错
        d = dict(row)
        # gobob_api_key 是机密, 非 owner/advisor 不显示
        if user.get("role") not in (auth.ROLE_OWNER, auth.ROLE_ADVISOR):
            d.pop("gobob_api_key", None)
        return d


@router.put("/me")
def update_my_org(
    req: OrgMeUpdateReq,
    user: dict = Depends(auth.require_owner),
    org_id: str = Depends(get_org_id),
):
    """仅 owner 可改本机构信息. None 字段不改 (PATCH 语义), 空字符串清空."""
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        return {"updated": 0}
    # name 列允许空字符串吗? schema 是 NOT NULL, 不允许. 如果传空串, 报错.
    if "name" in fields and not fields["name"].strip():
        raise HTTPException(status_code=400, detail="机构名不能为空")

    set_clauses = ", ".join(f"{k}=%s" for k in fields.keys())
    params = list(fields.values()) + [org_id]
    with db_cursor() as cur:
        cur.execute(
            f"UPDATE orgs SET {set_clauses} WHERE id=%s",
            params,
        )
    return {"updated": len(fields)}