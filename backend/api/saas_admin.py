"""
api/saas_admin.py — SOHO SaaS 运营后台 API
=====================================================

Gobob 运营方 (小Z 等) 管理 SOHO SaaS 版的所有机构:
  - 机构账户 + 订阅计费 (免费版 <=2 协作账号, >=3 每账号 ¥1000/年)
  - 机构开通 / 停用 (欠费或违规)
  - SaaS 机构 Gobob Data API 用量 (走官方主 Key, 不限次但要防滥用/算成本)
  - 收费/账单流水 (台账, 不接在线支付)

跟 Gobob 主站的 admin 完全独立 — SOHO 是独立运营项目, 只调 Gobob Data API.

认证: 独立的 saas_ops_admins 表 (不是机构 accounts/members),
      token role="saas_ops", org_id="_ops_", 跟任何机构身份天然隔离.

路由前缀: /api/saas
"""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor
from core.id_gen import new_id, new_order_no

log = logging.getLogger("saas_admin")

router = APIRouter(prefix="/api/saas", tags=["saas-admin"])

OPS_ROLE = "saas_ops"
OPS_ORG = "_ops_"


# ── 认证 ─────────────────────────────────────────────────────────

def get_ops_admin(authorization: str = Header(None)) -> dict:
    """运营后台登录态. 独立于机构账号 — 只认 saas_ops_admins 表."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权 (请用 Bearer token 登录)")
    payload = auth.decode_token(authorization[7:])
    if not payload or payload.get("role") != OPS_ROLE:
        raise HTTPException(status_code=401, detail="Token 无效或非运营账号")
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, username, name, is_super, status FROM saas_ops_admins WHERE id=%s LIMIT 1",
            (payload.get("sub"),),
        )
        row = cur.fetchone()
    if not row or row["status"] != "active":
        raise HTTPException(status_code=401, detail="运营账号不存在或已停用")
    return dict(row)


class OpsLoginReq(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/login")
def ops_login(req: OpsLoginReq):
    """运营后台登录. 账号在 saas_ops_admins 表, 由运维手动插入 (不开放注册)."""
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, name, status FROM saas_ops_admins WHERE username=%s LIMIT 1",
            (req.username,),
        )
        row = cur.fetchone()
        if not row or not auth.verify_password(req.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if row["status"] != "active":
            raise HTTPException(status_code=403, detail="账号已停用")
        cur.execute("UPDATE saas_ops_admins SET last_login_at=NOW() WHERE id=%s", (row["id"],))
    token = auth.create_token(row["id"], row["username"], OPS_ROLE, OPS_ORG)
    return {"token": token, "admin": {"id": row["id"], "username": row["username"], "name": row["name"]}}


@router.get("/me")
def ops_me(admin: dict = Depends(get_ops_admin)):
    return admin


# ── 机构账户 + 订阅计费 ───────────────────────────────────────────

# 协作账号 = owner + advisor (不含 student/parent, 学生/家长不占席位)
COLLAB_ROLES = ("owner", "advisor")
FREE_SEATS = 2           # 1-2 协作账号免费
SEAT_PRICE = 1000.0      # ¥/账号/年


def _org_with_seats(cur, org_row: dict) -> dict:
    """给 org 行加上: 实时协作账号数 / 应收年费 / 是否超免."""
    cur.execute(
        "SELECT role, COUNT(*) AS c FROM members WHERE org_id=%s GROUP BY role",
        (org_row["id"],),
    )
    role_counts = {r["role"]: r["c"] for r in cur.fetchall()}
    collab = sum(role_counts.get(r, 0) for r in COLLAB_ROLES)
    org_row["seats_collab"] = collab
    org_row["seats_student"] = role_counts.get("student", 0)
    org_row["seats_parent"] = role_counts.get("parent", 0)
    org_row["seats_total"] = sum(role_counts.values())
    # 应收: 超过免费 2 席的部分, 每席 ¥1000/年 (plan_status=paid 才真收)
    billable = max(0, collab - FREE_SEATS)
    org_row["seats_billable"] = billable
    org_row["annual_fee"] = billable * SEAT_PRICE
    org_row["is_over_free"] = collab > FREE_SEATS
    return org_row


@router.get("/orgs")
def list_orgs(
    admin: dict = Depends(get_ops_admin),
    status: str | None = Query(None, description="free/trial/paid/suspended"),
    q: str | None = Query(None, description="按机构名搜索"),
):
    """机构列表 — 每个机构的订阅状态 + 协作账号数 + 应收年费."""
    where, params = [], []
    if status:
        where.append("o.plan_status = %s")
        params.append(status)
    if q:
        where.append("o.name LIKE %s")
        params.append(f"%{q}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT o.* FROM orgs o {where_sql} ORDER BY o.created_at DESC""",
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]
        items = [_org_with_seats(cur, r) for r in rows]
    # 汇总
    summary = {
        "total_orgs": len(items),
        "paid_orgs": sum(1 for i in items if i["plan_status"] == "paid"),
        "free_orgs": sum(1 for i in items if i["plan_status"] == "free"),
        "suspended_orgs": sum(1 for i in items if i["plan_status"] == "suspended"),
        "total_annual_fee": sum(i["annual_fee"] for i in items if i["plan_status"] == "paid"),
    }
    for it in items:
        for f in ("created_at", "updated_at", "paid_until"):
            if it.get(f):
                it[f] = str(it[f])
        it.pop("gobob_api_key", None)  # 不下发 key
    return {"summary": summary, "items": items}


@router.get("/orgs/{org_id}")
def org_detail(org_id: str, admin: dict = Depends(get_ops_admin)):
    """单个机构详情: 基本信息 + 席位 + 账单 + 近30天 API 用量."""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM orgs WHERE id=%s", (org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="机构不存在")
        org = _org_with_seats(cur, dict(row))
        # 账单
        cur.execute(
            "SELECT * FROM saas_invoices WHERE org_id=%s ORDER BY created_at DESC LIMIT 50",
            (org_id,),
        )
        invoices = [dict(r) for r in cur.fetchall()]
        # 近 30 天 API 用量
        cur.execute(
            """SELECT usage_date, endpoint, calls FROM saas_api_usage
               WHERE org_id=%s AND usage_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
               ORDER BY usage_date DESC, calls DESC""",
            (org_id,),
        )
        usage = [dict(r) for r in cur.fetchall()]
    for f in ("created_at", "updated_at", "paid_until"):
        if org.get(f):
            org[f] = str(org[f])
    org.pop("gobob_api_key", None)
    for inv in invoices:
        for f in ("period_start", "period_end", "paid_at", "created_at", "updated_at"):
            if inv.get(f):
                inv[f] = str(inv[f])
        inv["amount"] = float(inv["amount"])
        inv["unit_price"] = float(inv["unit_price"])
    for u in usage:
        u["usage_date"] = str(u["usage_date"])
    return {"org": org, "invoices": invoices, "usage_30d": usage}


class OrgUpdateReq(BaseModel):
    plan_status: str | None = None  # free/trial/paid/suspended
    seats_paid: int | None = None
    paid_until: str | None = None   # YYYY-MM-DD
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    name: str | None = None


@router.put("/orgs/{org_id}")
def update_org(org_id: str, req: OrgUpdateReq, admin: dict = Depends(get_ops_admin)):
    """更新机构订阅信息 (运营手动维护台账)."""
    fields, params = [], []
    for k in ("plan_status", "seats_paid", "paid_until", "contact_name", "contact_phone", "contact_email", "name"):
        v = getattr(req, k)
        if v is not None:
            fields.append(f"{k} = %s")
            params.append(v)
    if not fields:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    params.append(org_id)
    with db_cursor() as cur:
        cur.execute(f"UPDATE orgs SET {', '.join(fields)} WHERE id=%s", params)
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="机构不存在")
    log.info("ops %s updated org %s: %s", admin["username"], org_id, req.dict(exclude_none=True))
    return {"ok": True}


@router.post("/orgs/{org_id}/disable")
def disable_org(org_id: str, admin: dict = Depends(get_ops_admin)):
    """停用机构 (欠费/违规) — 停用后全机构登不进."""
    with db_cursor() as cur:
        cur.execute("UPDATE orgs SET disabled=1 WHERE id=%s", (org_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="机构不存在")
    log.warning("ops %s DISABLED org %s", admin["username"], org_id)
    return {"ok": True, "disabled": True}


@router.post("/orgs/{org_id}/enable")
def enable_org(org_id: str, admin: dict = Depends(get_ops_admin)):
    """恢复机构."""
    with db_cursor() as cur:
        cur.execute("UPDATE orgs SET disabled=0 WHERE id=%s", (org_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="机构不存在")
    log.info("ops %s enabled org %s", admin["username"], org_id)
    return {"ok": True, "disabled": False}


# ── 收费/账单流水 ─────────────────────────────────────────────────

class InvoiceCreateReq(BaseModel):
    org_id: str
    seats: int = Field(..., gt=0)
    unit_price: float = SEAT_PRICE
    period_start: str  # YYYY-MM-DD
    period_end: str
    note: str | None = None


@router.post("/invoices")
def create_invoice(req: InvoiceCreateReq, admin: dict = Depends(get_ops_admin)):
    """开账单 (台账). amount 自动 = seats * unit_price."""
    amount = round(req.seats * req.unit_price, 2)
    iid = new_id()
    invoice_no = new_order_no("SO")
    with db_cursor() as cur:
        cur.execute("SELECT id FROM orgs WHERE id=%s", (req.org_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="机构不存在")
        cur.execute(
            """INSERT INTO saas_invoices
               (id, org_id, invoice_no, seats, unit_price, amount, period_start, period_end, note, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (iid, req.org_id, invoice_no, req.seats, req.unit_price, amount,
             req.period_start, req.period_end, req.note, admin["id"]),
        )
    log.info("ops %s created invoice %s for org %s: ¥%s", admin["username"], invoice_no, req.org_id, amount)
    return {"ok": True, "id": iid, "invoice_no": invoice_no, "amount": amount}


class InvoicePayReq(BaseModel):
    payment_method: str | None = None


@router.post("/invoices/{invoice_id}/pay")
def mark_invoice_paid(invoice_id: str, req: InvoicePayReq, admin: dict = Depends(get_ops_admin)):
    """标记账单已收 — 同时把机构的 plan_status 置 paid + 更新 seats_paid/paid_until."""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM saas_invoices WHERE id=%s", (invoice_id,))
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="账单不存在")
        if inv["status"] == "paid":
            raise HTTPException(status_code=400, detail="账单已是已收状态")
        cur.execute(
            "UPDATE saas_invoices SET status='paid', paid_at=NOW(), payment_method=%s WHERE id=%s",
            (req.payment_method, invoice_id),
        )
        # 同步机构订阅状态
        cur.execute(
            "UPDATE orgs SET plan_status='paid', seats_paid=%s, paid_until=%s WHERE id=%s",
            (inv["seats"], inv["period_end"], inv["org_id"]),
        )
    log.info("ops %s marked invoice %s paid (org %s)", admin["username"], inv["invoice_no"], inv["org_id"])
    return {"ok": True}


@router.post("/invoices/{invoice_id}/void")
def void_invoice(invoice_id: str, admin: dict = Depends(get_ops_admin)):
    """作废账单."""
    with db_cursor() as cur:
        cur.execute("UPDATE saas_invoices SET status='void' WHERE id=%s AND status='pending'", (invoice_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=400, detail="账单不存在或已处理")
    return {"ok": True}


@router.get("/invoices")
def list_invoices(
    admin: dict = Depends(get_ops_admin),
    status: str | None = Query(None),
    org_id: str | None = Query(None),
):
    """账单列表 (全机构)."""
    where, params = [], []
    if status:
        where.append("i.status = %s")
        params.append(status)
    if org_id:
        where.append("i.org_id = %s")
        params.append(org_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT i.*, o.name AS org_name
                FROM saas_invoices i JOIN orgs o ON o.id = i.org_id
                {where_sql} ORDER BY i.created_at DESC LIMIT 200""",
            params,
        )
        items = [dict(r) for r in cur.fetchall()]
    for inv in items:
        for f in ("period_start", "period_end", "paid_at", "created_at", "updated_at"):
            if inv.get(f):
                inv[f] = str(inv[f])
        inv["amount"] = float(inv["amount"])
        inv["unit_price"] = float(inv["unit_price"])
    summary = {
        "pending_amount": sum(i["amount"] for i in items if i["status"] == "pending"),
        "paid_amount": sum(i["amount"] for i in items if i["status"] == "paid"),
    }
    return {"summary": summary, "items": items}


# ── SaaS 机构 API 用量 ────────────────────────────────────────────

@router.get("/usage")
def usage_overview(
    admin: dict = Depends(get_ops_admin),
    days: int = Query(30, ge=1, le=90),
):
    """全机构 API 用量总览 (近 N 天, 按机构聚合)."""
    with db_cursor() as cur:
        cur.execute(
            """SELECT u.org_id, o.name AS org_name, SUM(u.calls) AS total_calls,
                      COUNT(DISTINCT u.usage_date) AS active_days,
                      MAX(u.usage_date) AS last_date
               FROM saas_api_usage u JOIN orgs o ON o.id = u.org_id
               WHERE u.usage_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
               GROUP BY u.org_id, o.name
               ORDER BY total_calls DESC""",
            (days,),
        )
        items = [dict(r) for r in cur.fetchall()]
        # 按端点汇总 (全机构)
        cur.execute(
            """SELECT endpoint, SUM(calls) AS calls FROM saas_api_usage
               WHERE usage_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
               GROUP BY endpoint ORDER BY calls DESC""",
            (days,),
        )
        by_endpoint = [dict(r) for r in cur.fetchall()]
    for it in items:
        it["last_date"] = str(it["last_date"]) if it.get("last_date") else None
    return {"days": days, "by_org": items, "by_endpoint": by_endpoint}
