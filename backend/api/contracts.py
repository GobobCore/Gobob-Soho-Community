"""
api/contracts.py — 签约管理（合同 + 线下收款）

机构自营：无支付网关、无平台抽成。合同选定服务模块组合（服务包），
线下收款分次登记（定金/中期/尾款）。
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id, new_order_no
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _can_see_all(user: dict) -> bool:
    return user.get("role") == auth.ROLE_OWNER


def _row(row) -> dict:
    d = dict(row)
    if d.get("modules") and isinstance(d["modules"], str):
        try:
            d["modules"] = json.loads(d["modules"])
        except Exception:
            pass
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        if hasattr(v, "isoformat") and not isinstance(v, str) and k.endswith("date"):
            d[k] = v.isoformat()
    return d


# ── 服务模块目录（机构可见，用于勾选服务包）──────────────────────

@router.get("/modules")
def list_modules(user: dict = Depends(auth.require_staff)):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, code, name_zh, name_en, category, description, base_price_cents "
            "FROM service_modules WHERE is_active=1 ORDER BY sort_order")
        rows = cur.fetchall()
    for r in rows:
        r["base_price"] = (r["base_price_cents"] or 0) / 100
        r.pop("base_price_cents", None)
    return {"modules": rows}


# ── 合同 CRUD ─────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    student_member_id: str
    lead_id: str | None = None
    modules: list[str] = Field(..., min_length=1, description="服务模块 code 列表")
    total_amount: float
    signed_date: str | None = None
    service_start: str | None = None
    service_end: str | None = None
    notes: str | None = None


@router.post("")
def create_contract(req: ContractCreate, user: dict = Depends(auth.require_staff),
                    org_id: str = Depends(get_org_id)):
    # 校验学生属于本机构
    with db_cursor() as cur:
        cur.execute(
            "SELECT id FROM members WHERE id=%s AND org_id=%s AND role='student'",
            (req.student_member_id, org_id))
        if not cur.fetchone():
            raise HTTPException(400, "学生不存在")
        # 校验模块合法
        cur.execute("SELECT code FROM service_modules WHERE is_active=1")
        valid = {r["code"] for r in cur.fetchall()}
    bad = [m for m in req.modules if m not in valid]
    if bad:
        raise HTTPException(400, f"无效服务模块：{bad}")

    cid = new_id()
    cno = new_order_no("CT")
    with db_transaction() as cur:
        cur.execute(
            """INSERT INTO contracts
               (id, org_id, contract_no, student_member_id, lead_id, modules, total_amount,
                signed_date, service_start, service_end, status, notes, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s,%s)""",
            (cid, org_id, cno, req.student_member_id, req.lead_id, json.dumps(req.modules),
             req.total_amount, req.signed_date, req.service_start, req.service_end,
             req.notes, user.get("member_id")),
        )
        # 审计
        cur.execute(
            """INSERT INTO audit_log (id, org_id, actor_member_id, action, target_type, target_id, detail)
               VALUES (%s,%s,%s,'contract_sign','contract',%s,%s)""",
            (new_id(), org_id, user.get("member_id"), cid,
             json.dumps({"contract_no": cno, "amount": req.total_amount})),
        )
    return {"contract_id": cid, "contract_no": cno}


@router.get("")
def list_contracts(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id),
                   status: str | None = None, student_id: str | None = None,
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    where = ["c.org_id=%s"]
    params = [org_id]
    if status:
        where.append("c.status=%s")
        params.append(status)
    if student_id:
        where.append("c.student_member_id=%s")
        params.append(student_id)
    sql_where = " AND ".join(where)
    offset = (page - 1) * page_size
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM contracts c WHERE {sql_where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT c.*, m.name AS student_name,
                  (SELECT COALESCE(SUM(amount),0) FROM contract_payments p
                    WHERE p.contract_id=c.id) AS paid_amount
                FROM contracts c LEFT JOIN members m ON m.id=c.student_member_id
                WHERE {sql_where} ORDER BY c.created_at DESC LIMIT %s OFFSET %s""",
            params + [page_size, offset])
        rows = [_row(r) for r in cur.fetchall()]
    return {"total": total, "items": rows}


@router.get("/{contract_id}")
def contract_detail(contract_id: str, user: dict = Depends(auth.get_current_user),
                    org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute(
            """SELECT c.*, m.name AS student_name FROM contracts c
               LEFT JOIN members m ON m.id=c.student_member_id
               WHERE c.id=%s AND c.org_id=%s""", (contract_id, org_id))
        c = cur.fetchone()
        if not c:
            raise HTTPException(404, "合同不存在")
        # 学生/家长只能看自己的
        if user["role"] in (auth.ROLE_STUDENT, auth.ROLE_PARENT):
            if c["student_member_id"] != user.get("member_id"):
                # parent 需确认关联
                cur.execute(
                    "SELECT 1 FROM member_relationships WHERE from_member_id=%s AND to_member_id=%s",
                    (user.get("member_id"), c["student_member_id"]))
                if not cur.fetchone():
                    raise HTTPException(403, "无权查看")
        cur.execute(
            "SELECT * FROM contract_payments WHERE contract_id=%s ORDER BY paid_at DESC, created_at DESC",
            (contract_id,))
        payments = [_row(p) for p in cur.fetchall()]
    out = _row(c)
    out["payments"] = payments
    out["paid_amount"] = sum(p["amount"] for p in payments)
    return out


class ContractStatusReq(BaseModel):
    status: str  # active/completed/terminated


@router.post("/{contract_id}/status")
def update_status(contract_id: str, req: ContractStatusReq,
                  user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    if req.status not in ("active", "completed", "terminated"):
        raise HTTPException(400, "无效状态")
    with db_cursor() as cur:
        cur.execute("UPDATE contracts SET status=%s WHERE id=%s AND org_id=%s",
                    (req.status, contract_id, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "合同不存在")
    return {"ok": True}


# ── 收款登记 ──────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0)
    pay_type: str | None = None
    pay_method: str | None = None
    paid_at: str | None = None
    note: str | None = None


@router.post("/{contract_id}/payments")
def add_payment(contract_id: str, req: PaymentCreate,
                user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("SELECT id FROM contracts WHERE id=%s AND org_id=%s", (contract_id, org_id))
        if not cur.fetchone():
            raise HTTPException(404, "合同不存在")
        pid = new_id()
        cur.execute(
            """INSERT INTO contract_payments
               (id, org_id, contract_id, amount, pay_type, pay_method, paid_at, note, recorded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (pid, org_id, contract_id, req.amount, req.pay_type, req.pay_method,
             req.paid_at, req.note, user.get("member_id")),
        )
    return {"payment_id": pid}
