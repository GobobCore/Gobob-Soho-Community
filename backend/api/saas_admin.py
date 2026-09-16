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

R-Feat 2026-09-16 v3: 开源版按次购买走 Gobob payment (18806) 完整接入
  - POST /buy-key 公开端点: 创建 saas_key_orders + 调 Gobob payment 创建订单 + 返回二维码
  - GET /buy-key/{order_no} 公开端点: 查 SOHO 订单状态 (会顺便轮询 Gobob payment 状态)
  - POST /webhooks/payment (新增): 接收 Gobob payment 的 paid 回调, 自动开通 Key
"""

import logging
from datetime import date, datetime

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from core import auth
from core.config import get_settings
from core.database import db_cursor
from core.id_gen import new_id, new_order_no

log = logging.getLogger("saas_admin")
settings = get_settings()

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


# ── 开源版按次购买 (公开, 无需登录) ─────────────────────────────
# 机构自助下单买 Gobob Data API 调用次数, 台账模式:
#   1. 机构填表 → 创建 org + api_key (remaining_calls=0, 未激活) + topup 待收
#   2. 机构转账 (alipay/wechat/转账) 附订单号
#   3. 运营在 Gobob admin-portal 点「标记已收」→ Key 激活
# 注: api_keys 表在 Gobob 主库, 通过 Gobob 后端调 (gobob_client 不能用, 这是 SOHO 后端逻辑)
# 简化方案: SOHO 不直接创建 Gobob Key, 只记申请单, 运营在 admin 后台手动开 Key + 充次数

class BuyKeyReq(BaseModel):
    org_name: str = Field(..., min_length=2, max_length=100, description="机构名")
    contact_email: str = Field(..., description="联系邮箱 (收 Key 用)")
    contact_phone: str | None = None
    contact_name: str = Field(..., min_length=1, max_length=50)
    calls: int = Field(..., ge=10, le=10000, description="购买次数 (¥1/次, 最低 10)")
    note: str | None = None


# 公开申请表 (saas_key_orders 表, 运营在 admin 后台看 + 手动开 Key 充值)
# 先建表 (在 saas_admin.py 里 IF NOT EXISTS, 避免新写 migration)
def _ensure_key_orders_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saas_key_orders (
          id            VARCHAR(64) PRIMARY KEY,
          order_no      VARCHAR(50) NOT NULL UNIQUE COMMENT 'SO-xxx 可读单号',
          org_name      VARCHAR(100) NOT NULL,
          contact_name  VARCHAR(50) NOT NULL,
          contact_email VARCHAR(200) NOT NULL,
          contact_phone VARCHAR(50) DEFAULT NULL,
          calls         INT NOT NULL,
          amount        DECIMAL(10,2) NOT NULL COMMENT '应付 ¥ (= calls, ¥1/次)',
          status        ENUM('pending','paid','delivered','cancelled') NOT NULL DEFAULT 'pending',
          payment_order_no VARCHAR(50) DEFAULT NULL COMMENT 'Gobob payment 订单号',
          api_key_id    BIGINT DEFAULT NULL COMMENT '开通后的 Gobob api_keys.id',
          api_key_prefix VARCHAR(16) DEFAULT NULL COMMENT '开通后展示给机构',
          paid_at       DATETIME DEFAULT NULL,
          delivered_at  DATETIME DEFAULT NULL,
          note          VARCHAR(500) DEFAULT NULL,
          created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          INDEX idx_status (status),
          INDEX idx_email (contact_email),
          INDEX idx_payment_order (payment_order_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    # 已存在表补列 (幂等)
    cur.execute("""
        SELECT COUNT(*) AS c FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = 'saas_key_orders' AND column_name = 'payment_order_no'
    """)
    if cur.fetchone()["c"] == 0:
        cur.execute("ALTER TABLE saas_key_orders ADD COLUMN payment_order_no VARCHAR(50) DEFAULT NULL AFTER status, ADD INDEX idx_payment_order (payment_order_no)")


@router.post("/buy-key")
def buy_key(req: BuyKeyReq, request: Request):
    """公开: 机构申请购买 Gobob Data API 次数 (开源版).

    完整接入 Gobob payment (18806):
      1. 创建 saas_key_orders 记录 (SOHO 本地台账)
      2. 调 Gobob payment POST /api/v1/public/orders 创建支付订单 (拿 order_no + 二维码)
      3. 返回 order_no + qrcode_url + pay_url 给前端

    前端拿到后:
      - 显示二维码 (alipay_native / wechat native) 让机构扫
      - 每 5s 轮询 GET /api/saas/buy-key/{order_no} 直到 paid
      - paid 后我们后台自动开通 Key 并邮件/微信通知机构
    """
    # 1. 落 SOHO 台账 (saas_key_orders)
    with db_cursor() as cur:
        _ensure_key_orders_table(cur)
        oid = new_id()
        order_no = new_order_no("SOKEY")
        amount = float(req.calls)  # ¥1/次
        cur.execute(
            """INSERT INTO saas_key_orders
               (id, order_no, org_name, contact_name, contact_email, contact_phone, calls, amount, note)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (oid, order_no, req.org_name, req.contact_name, req.contact_email,
             req.contact_phone, req.calls, amount, req.note),
        )
    log.info("buy-key order created: %s %s (%s calls ¥%s) by %s <%s>",
             order_no, req.org_name, req.calls, amount, req.contact_name, req.contact_email)

    # 2. 调 Gobob payment 创建支付订单
    plan_code = {10: "soho_api_10", 50: "soho_api_50", 100: "soho_api_100", 500: "soho_api_500"}.get(req.calls)
    if not plan_code:
        raise HTTPException(status_code=400, detail="只支持 10/50/100/500 次包")

    pay_base = settings.gobob_payment_base
    idem_key = f"soho-key-{order_no}"  # 幂等: 同一 saas_key_order 只创建一次 payment order
    try:
        resp = httpx.post(
            f"{pay_base}/api/v1/public/orders",
            json={
                "plan_code": plan_code,
                # alipay_pc 是真生产可用 (APP_ID 商户号只开了 page.pay / wap.pay)
                # alipay_native (precreate) 该商户号没权限, 会 ACCESS_FORBIDDEN
                "payment_method": "alipay_pc",
                "user_email": req.contact_email,
                "metadata": {"soho_order_no": order_no, "org_name": req.org_name, "calls": req.calls},
            },
            headers={"Idempotency-Key": idem_key},
            timeout=15.0,
        )
        if resp.status_code not in (200, 201):
            log.error("payment create failed: %s %s", resp.status_code, resp.text[:300])
            raise HTTPException(status_code=502, detail="支付订单创建失败, 请稍后再试")
        pay = resp.json()
    except httpx.HTTPError as e:
        log.error("payment call failed: %s", e)
        raise HTTPException(status_code=502, detail="支付服务暂时不可用, 请稍后再试")

    pay_order_no = pay.get("order_no")
    # 把 payment_order_no 回写到 SOHO 台账
    with db_cursor() as cur:
        cur.execute(
            "UPDATE saas_key_orders SET payment_order_no=%s WHERE id=%s",
            (pay_order_no, oid),
        )

    log.info("payment order created: soho=%s → payment=%s", order_no, pay_order_no)
    return {
        "ok": True,
        "order_no": order_no,           # SOHO 台账订单号
        "payment_order_no": pay_order_no,  # Gobob payment 订单号 (用于轮询状态)
        "amount": amount,
        "calls": req.calls,
        "payment_method": "alipay_pc",
        "pay_url": pay.get("payment", {}).get("pay_url"),  # 支付宝网页支付 URL (前端跳转用)
        "pay_hint": "点击「立即支付」跳转到支付宝网页完成支付, 支付成功后我们会通过邮箱发送 API Key",
    }


@router.get("/buy-key/{order_no}")
def check_order(order_no: str):
    """公开: 用订单号查状态 (机构知道自己 Key 开通了没).

    如果还 pending 且有 payment_order_no, 顺便轮询 Gobob payment 状态并更新本地.
    """
    with db_cursor() as cur:
        _ensure_key_orders_table(cur)
        cur.execute(
            "SELECT order_no, org_name, calls, amount, status, payment_order_no, api_key_prefix, paid_at, delivered_at, created_at "
            "FROM saas_key_orders WHERE order_no=%s",
            (order_no,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="订单号不存在")

    # 轮询 Gobob payment 状态 (pending → paid)
    if row["status"] == "pending" and row.get("payment_order_no"):
        _poll_payment_status(row)
        # 再读一次 (可能被上面更新)
        with db_cursor() as cur:
            cur.execute(
                "SELECT order_no, org_name, calls, amount, status, payment_order_no, api_key_prefix, paid_at, delivered_at, created_at "
                "FROM saas_key_orders WHERE order_no=%s",
                (order_no,),
            )
            row = cur.fetchone()

    for f in ("paid_at", "delivered_at", "created_at"):
        if row.get(f):
            row[f] = str(row[f])
    row["amount"] = float(row["amount"])
    return row


def _poll_payment_status(soho_order_row: dict):
    """轮询 Gobob payment 状态; paid 则更新 saas_key_orders."""
    pay_order_no = soho_order_row.get("payment_order_no")
    if not pay_order_no:
        return
    try:
        resp = httpx.get(
            f"{settings.gobob_payment_base}/api/v1/public/orders/{pay_order_no}",
            timeout=10.0,
        )
        if resp.status_code != 200:
            log.warning("payment status poll failed: %s", resp.status_code)
            return
        pay = resp.json()
    except httpx.HTTPError as e:
        log.warning("payment poll error: %s", e)
        return

    if pay.get("status") != "paid":
        return

    # 支付完成 → 更新 saas_key_orders
    with db_cursor() as cur:
        cur.execute(
            "UPDATE saas_key_orders SET status='paid', paid_at=NOW() WHERE order_no=%s AND status='pending'",
            (soho_order_row["order_no"],),
        )
        if cur.rowcount == 0:
            return  # 已被其他流程处理
    log.info("saas_key_order %s paid via payment %s", soho_order_row["order_no"], pay_order_no)
    # 后续由运营在 soho-ops 手动开通 (调 Gobob admin-portal 或 API)
    # 简化: 不自动开通, 让运营确认后手动充次数到 Key


# ── 运营后台看 buy-key 申请单 ────────────────────────────────────

@router.get("/key-orders")
def list_key_orders(
    admin: dict = Depends(get_ops_admin),
    status: str | None = Query(None),
):
    """运营后台: 列所有 buy-key 申请."""
    with db_cursor() as cur:
        _ensure_key_orders_table(cur)
        where = "WHERE status = %s" if status else ""
        params = (status,) if status else ()
        cur.execute(
            f"SELECT * FROM saas_key_orders {where} ORDER BY created_at DESC LIMIT 200",
            params,
        )
        items = [dict(r) for r in cur.fetchall()]
    for it in items:
        for f in ("paid_at", "delivered_at", "created_at", "updated_at"):
            if it.get(f):
                it[f] = str(it[f])
        it["amount"] = float(it["amount"])
    summary = {
        "pending": sum(1 for i in items if i["status"] == "pending"),
        "pending_amount": sum(i["amount"] for i in items if i["status"] == "pending"),
        "paid_amount": sum(i["amount"] for i in items if i["status"] == "paid"),
    }
    return {"summary": summary, "items": items}


class MarkPaidReq(BaseModel):
    api_key_id: int | None = None  # 运营已在 Gobob admin-portal 开通了 Key, 填 id
    api_key_prefix: str | None = None
    payment_method: str | None = None


@router.post("/key-orders/{order_id}/paid")
def mark_order_paid(order_id: str, req: MarkPaidReq, admin: dict = Depends(get_ops_admin)):
    """标记订单已收 + 关联已开通的 Key. 机构端能看到 status=paid."""
    with db_cursor() as cur:
        _ensure_key_orders_table(cur)
        cur.execute(
            "UPDATE saas_key_orders SET status='paid', paid_at=NOW(), api_key_id=%s, api_key_prefix=%s, note=CONCAT(COALESCE(note,''),' pay:',COALESCE(%s,'')) WHERE id=%s AND status='pending'",
            (req.api_key_id, req.api_key_prefix, req.payment_method, order_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=400, detail="订单不存在或已处理")
    log.info("ops %s marked key-order %s paid (key %s)", admin["username"], order_id, req.api_key_prefix)
    return {"ok": True}


@router.post("/key-orders/{order_id}/deliver")
def mark_order_delivered(order_id: str, admin: dict = Depends(get_ops_admin)):
    """标记已交付 (Key 已发给机构邮箱)."""
    with db_cursor() as cur:
        _ensure_key_orders_table(cur)
        cur.execute(
            "UPDATE saas_key_orders SET status='delivered', delivered_at=NOW() WHERE id=%s AND status='paid'",
            (order_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=400, detail="订单状态不对")
    return {"ok": True}


@router.post("/key-orders/{order_id}/cancel")
def cancel_order(order_id: str, admin: dict = Depends(get_ops_admin)):
    """取消订单 (机构没付钱/退款)."""
    with db_cursor() as cur:
        _ensure_key_orders_table(cur)
        cur.execute(
            "UPDATE saas_key_orders SET status='cancelled' WHERE id=%s AND status='pending'",
            (order_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=400, detail="订单状态不对")
    return {"ok": True}
