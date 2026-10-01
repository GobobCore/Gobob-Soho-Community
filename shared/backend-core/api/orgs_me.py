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
    slug: str | None = Field(None, min_length=2, max_length=64, pattern=r"^[a-zA-Z][a-zA-Z0-9-]*$", description="英文数字ID (机构专属链接, 必须以字母开头)")
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
            """SELECT id, name, slug, description, address, phone, email, website, logo_url,
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
    if "name" in fields and not fields["name"].strip():
        raise HTTPException(status_code=400, detail="机构名不能为空")
    # slug 唯一性校验
    if "slug" in fields:
        slug = fields["slug"]
        if re.match(r'^[0-9]+$', slug):
            raise HTTPException(status_code=400, detail="slug 不能是纯数字")
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9-]*$', slug):
            raise HTTPException(status_code=400, detail="slug 必须以字母开头, 只能包含英文/数字/横线")
        with db_cursor() as cur:
            cur.execute("SELECT id FROM orgs WHERE slug=%s AND id!=%s LIMIT 1", (slug, org_id))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail=f"slug '{slug}' 已被其他机构占用")
    set_clauses = ", ".join(f"{k}=%s" for k in fields.keys())
    params = list(fields.values()) + [org_id]
    with db_cursor() as cur:
        cur.execute(
            f"UPDATE orgs SET {set_clauses} WHERE id=%s",
            params,
        )
    return {"updated": len(fields)}


# ── 订单及用量 (owner 视图) ─────────────────────────────────────

# SaaS 计费表由 saas/backend/api/saas_admin.py 在运行时 DDL 创建, 不在
# shared/backend-core/sql/schema.sql 里。社区版不挂 saas router, 因此这三张表
# 在社区部署中根本不存在。
#
# R-Fix 2026-10-01: 本模块属于 shared 层, 社区版与 SaaS 版共用, 因此查询前
# 必须探测表是否存在 —— 否则社区版调用本端点必然 500 (table doesn't exist)。
# 表缺失时返回 billing_available=false + 空值, 前端按"无计费"优雅展示。
_SAAS_TABLES = ("saas_api_usage", "saas_key_orders", "saas_invoices")

# 探测结果按进程缓存: 表结构不会在运行期变化, 无需每次请求都查 information_schema
_table_exists_cache: dict[str, bool] = {}


def _table_exists(cur, table: str) -> bool:
    """当前库是否存在指定表 (带进程级缓存)。"""
    if table not in _table_exists_cache:
        try:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
                (table,),
            )
            _table_exists_cache[table] = cur.fetchone() is not None
        except Exception:
            # 权限不足 / 连接异常时保守当作"不存在", 不让探测本身打断请求
            _table_exists_cache[table] = False
    return _table_exists_cache[table]


@router.get("/me/usage")
def get_org_usage(
    user: dict = Depends(auth.get_current_user),
    org_id: str = Depends(get_org_id),
):
    """返回当前机构的套餐 / 用量 / 订单（订单及用量页面）.

    社区版无 SaaS 计费表时返回 billing_available=false, 套餐与成员统计仍可用。
    """
    with db_cursor() as cur:
        # 配额 & 套餐
        cur.execute(
            "SELECT plan_status, seats_paid, paid_until FROM orgs WHERE id=%s",
            (org_id,),
        )
        org = cur.fetchone()
        cur.execute(
            """SELECT role, COUNT(*) AS c FROM members
               WHERE org_id=%s AND is_active=1 AND is_virtual=0
               GROUP BY role""",
            (org_id,),
        )
        by_role = {r["role"]: r["c"] for r in cur.fetchall()}

        # ── 以下三张表仅 SaaS 版存在, 社区版整段跳过 ──
        has_usage = _table_exists(cur, "saas_api_usage")
        has_key_orders = _table_exists(cur, "saas_key_orders")
        has_invoices = _table_exists(cur, "saas_invoices")
        billing_available = has_usage or has_key_orders or has_invoices

        # API 调用统计 (本月 + 累计)
        total_calls = month_calls = year_calls = 0
        if has_usage:
            cur.execute(
                """SELECT SUM(calls) AS total_calls
                   FROM saas_api_usage WHERE org_id=%s""",
                (org_id,),
            )
            total_calls = cur.fetchone()["total_calls"] or 0
            cur.execute(
                """SELECT SUM(calls) AS month_calls
                   FROM saas_api_usage WHERE org_id=%s
                   AND usage_date >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')""",
                (org_id,),
            )
            month_calls = cur.fetchone()["month_calls"] or 0
            cur.execute(
                """SELECT SUM(calls) AS year_calls
                   FROM saas_api_usage WHERE org_id=%s
                   AND usage_date >= DATE_FORMAT(CURDATE(), '%%Y-01-01')""",
                (org_id,),
            )
            year_calls = cur.fetchone()["year_calls"] or 0

        # 已购资源包总次数 (已交付状态)
        # R-Fix 2026-10-01: 原按 org_name 关联, 机构改名后历史订单全部孤儿化。
        # 优先按 org_id 关联 (P2.2 migration 加列后可用), 回落到 org_name 兼容旧数据。
        purchased_calls = 0
        if has_key_orders:
            cur.execute(
                """SELECT COALESCE(SUM(calls),0) AS total_purchased
                   FROM saas_key_orders
                   WHERE status='delivered'
                     AND (org_id = %s OR (org_id IS NULL
                          AND org_name = (SELECT name FROM orgs WHERE id=%s)))""",
                (org_id, org_id),
            )
            row = cur.fetchone()
            purchased_calls = (row or {}).get("total_purchased") or 0

        # 账单
        invoices = []
        if has_invoices:
            cur.execute(
                """SELECT invoice_no, seats, amount, period_start, period_end, status, paid_at, note
                   FROM saas_invoices WHERE org_id=%s ORDER BY created_at DESC LIMIT 10""",
                (org_id,),
            )
            for r in cur.fetchall():
                d = dict(r)
                for k in ("period_start", "period_end", "paid_at"):
                    d[k] = str(d[k]) if d.get(k) else None
                invoices.append(d)

        # 按次购买订单
        key_orders = []
        if has_key_orders:
            cur.execute(
                """SELECT order_no, calls, amount, status, payment_order_no, note, created_at
                   FROM saas_key_orders
                   WHERE org_id = %s
                      OR (org_id IS NULL
                          AND org_name = (SELECT name FROM orgs WHERE id=%s))
                   ORDER BY created_at DESC LIMIT 20""",
                (org_id, org_id),
            )
            for r in cur.fetchall():
                d = dict(r)
                d["created_at"] = str(d["created_at"]) if d.get("created_at") else None
                d["amount"] = float(d["amount"]) if d.get("amount") else None
                key_orders.append(d)

    plan_status = org["plan_status"] if org else "free"
    paid_until = str(org["paid_until"]) if org and org.get("paid_until") else None

    return {
        "billing_available": billing_available,
        "plan": {
            "status": plan_status,
            "seats_paid": (org["seats_paid"] or 0) if org else 0,
            "paid_until": paid_until,
        },
        "members": {
            "owner": by_role.get("owner", 0),
            "advisor": by_role.get("advisor", 0),
            "student": by_role.get("student", 0),
            "parent": by_role.get("parent", 0),
            "total": sum(by_role.values()),
        },
        "api_calls": {
            "total": total_calls,
            "this_month": month_calls,
            "this_year": year_calls,
            "purchased": purchased_calls,
            "annual_quota": 120,
            "monthly_quota": 10,
        },
        "invoices": invoices,
        "key_orders": key_orders,
    }