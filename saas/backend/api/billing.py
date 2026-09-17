"""
cloud/backend-saas/api/billing.py — SOHO SaaS 计费
=====================================================

商业模式 (按 PM 2026-09-16 确认):
- 免费 2 协作账号 (owner + advisor)
- ≥3 协作账号, 每账号 ¥1000/年
- 例: 5 账号 ¥3000/年, 10 账号 ¥8000/年 (年付一次)
- 开源版按次购买 ¥1/次, 走 Gobob payment (sibling module saas_key_orders)

SaaS 版额外要求:
- 运营手动开账单 (saas_invoices 表已有)
- 运营手动标 paid (saas_admin /invoices/{id}/pay 端点)
- 到期自动停用 (本模块的 check_expiry)

未实现 (PM 说后做):
- 在线支付 (复用 Gobob payment alipay_pc)
- 自动邮件 / 短信催收
- 自助续费 / 升降级
"""

import logging
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import os
import sys

from core.database import db_cursor
from core.id_gen import new_id, new_order_no

# billing.py 被 main.py 用 importlib 直接加载 (不是包形式),
# 所以 from .saas_admin 失败. 改成 importlib 直接加载 saas_admin 模块共享 get_ops_admin
import importlib.util  # noqa: E402
_API_DIR = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("cloud.saas_admin", os.path.join(_API_DIR, "saas_admin.py"))
_saas_admin_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_saas_admin_mod)
get_ops_admin = _saas_admin_mod.get_ops_admin

log = logging.getLogger("saas_billing")

router = APIRouter(prefix="/api/saas/billing", tags=["saas-billing"])


# ── 业务参数 ──
FREE_SEATS = 2
SEAT_PRICE_YEARLY = 1000.0  # ¥/账号/年
COLLAB_ROLES = ("owner", "advisor")


# ── 纯函数: 给 role_counts dict, 算年费 ──
# 抽成纯函数好测 (不用 DB), 实际 calc_annual_fee_with_db 走 DB 取 role_counts 后调它
def calc_annual_fee_pure(role_counts: dict) -> dict:
    """role_counts = {role: count} → 算年费信息 (纯函数, 无 DB 依赖).

    规则:
    - collab = owner + advisor 数
    - billable = max(0, collab - FREE_SEATS)
    - annual_fee = billable × SEAT_PRICE_YEARLY
    - is_over_free = collab > FREE_SEATS
    """
    collab = sum(role_counts.get(r, 0) for r in COLLAB_ROLES)
    billable = max(0, collab - FREE_SEATS)
    return {
        "seats_collab": collab,
        "seats_billable": billable,
        "annual_fee": billable * SEAT_PRICE_YEARLY,
        "is_over_free": collab > FREE_SEATS,
    }


# ── 计算机构当前应付年费 (跟 saas_admin._org_with_seats 一致) ──
def calc_annual_fee(cur, org_id: str) -> dict:
    cur.execute(
        "SELECT role, COUNT(*) AS c FROM members WHERE org_id=%s GROUP BY role",
        (org_id,),
    )
    role_counts = {r["role"]: r["c"] for r in cur.fetchall()}
    return calc_annual_fee_pure(role_counts)


# ── 端点 ──

class GenerateReq(BaseModel):
    org_id: str
    period_start: str | None = None  # 默认今天
    period_end: str | None = None    # 默认 1 年后
    note: str | None = None


@router.post("/generate")
def generate_invoice(req: GenerateReq, admin: dict = Depends(get_ops_admin)):
    """运营手动生成账单 (按当前席数, 1 年期).

    若机构已有 pending 账单, 拒绝 (避免重复)
    """
    period_start = req.period_start or date.today().isoformat()
    period_end = req.period_end or (date.today() + timedelta(days=365)).isoformat()
    with db_cursor() as cur:
        # 查机构 + 算 fee
        cur.execute("SELECT id, name FROM orgs WHERE id=%s", (req.org_id,))
        org = cur.fetchone()
        if not org:
            raise HTTPException(404, "机构不存在")
        fee = calc_annual_fee(cur, req.org_id)
        if fee["annual_fee"] <= 0:
            raise HTTPException(400, f"机构未超免费席数 (协作账号 {fee['seats_collab']} ≤ 2), 不需要生成账单")
        # 检查未结清
        cur.execute("SELECT id FROM saas_invoices WHERE org_id=%s AND status='pending'", (req.org_id,))
        if cur.fetchone():
            raise HTTPException(400, "机构已有待收账单, 请先处理")
        # 生成
        iid = new_id()
        invoice_no = new_order_no("SO")
        cur.execute(
            """INSERT INTO saas_invoices
               (id, org_id, invoice_no, seats, unit_price, amount, period_start, period_end, note, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (iid, req.org_id, invoice_no, fee["seats_billable"], SEAT_PRICE_YEARLY,
             fee["annual_fee"], period_start, period_end, req.note, admin["username"]),
        )
    log.info("ops %s generated invoice %s for org %s: ¥%s (seats=%s)",
             admin["username"], invoice_no, req.org_id, fee["annual_fee"], fee["seats_billable"])
    return {
        "ok": True,
        "invoice_no": invoice_no,
        "amount": fee["annual_fee"],
        "seats": fee["seats_billable"],
        "period_start": period_start,
        "period_end": period_end,
    }


@router.post("/check-expiry")
def check_expiry(admin: dict = Depends(get_ops_admin)):
    """扫描所有 paid 机构, paid_until 过期 → 标 suspended.

    运营每天调一次 (或 cron 自动跑), 不需要手动每条处理.
    """
    today = date.today()
    suspended_orgs = []
    with db_cursor() as cur:
        cur.execute(
            """SELECT id, name, paid_until, plan_status
               FROM orgs
               WHERE plan_status='paid' AND paid_until IS NOT NULL AND paid_until < %s""",
            (today,),
        )
        expired = cur.fetchall()
        for org in expired:
            cur.execute(
                "UPDATE orgs SET plan_status='suspended' WHERE id=%s",
                (org["id"],),
            )
            suspended_orgs.append({"org_id": org["id"], "name": org["name"], "paid_until": str(org["paid_until"])})
    log.info("ops %s expired-check: suspended %d orgs", admin["username"], len(suspended_orgs))
    return {"ok": True, "suspended": suspended_orgs, "count": len(suspended_orgs)}


@router.post("/check-usage")
def check_usage_threshold(admin: dict = Depends(get_ops_admin)):
    """扫描所有 free 机构, 协作账号 ≥ 3 但没有 pending 账单 → 提示运营.

    帮助运营主动发现该出账的机构 (而不是等机构来付钱).
    """
    need_invoice = []
    with db_cursor() as cur:
        cur.execute(
            """SELECT id, name, plan_status FROM orgs
               WHERE disabled=0 AND plan_status IN ('free', 'trial')"""
        )
        candidates = cur.fetchall()
        for org in candidates:
            fee = calc_annual_fee(cur, org["id"])
            if fee["annual_fee"] > 0:
                # 查是否已有 pending 账单
                cur.execute("SELECT id FROM saas_invoices WHERE org_id=%s AND status='pending'", (org["id"],))
                if cur.fetchone():
                    continue
                need_invoice.append({
                    "org_id": org["id"],
                    "name": org["name"],
                    "seats_collab": fee["seats_collab"],
                    "seats_billable": fee["seats_billable"],
                    "annual_fee": fee["annual_fee"],
                })
    return {"need_invoice": need_invoice, "count": len(need_invoice)}
