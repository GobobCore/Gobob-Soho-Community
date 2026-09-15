"""
api/contracts.py — 签约管理（合同 + 明细项 + 收款 + 退费 + 续约）— Phase 5 升级

合同 → contract_items（每模块独立金额/状态/交付物关联）→ 线下收款登记。
支持退费、续约、家长代签。
"""

import json
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor, db_transaction
from core.id_gen import new_id, new_order_no
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/contracts", tags=["contracts"])

ITEM_STATUSES = {"pending", "in_progress", "delivered", "completed", "cancelled", "refunded"}


def _row(row):
    d = dict(row)
    if d.get("modules") and isinstance(d["modules"], str):
        try: d["modules"] = json.loads(d["modules"])
        except: pass
    for k, v in d.items():
        if isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
    return d


# ── 服务模块目录 ───────────────────────────────────────────────

@router.get("/modules")
def list_modules(user: dict = Depends(auth.get_current_user)):
    with db_cursor() as cur:
        cur.execute("SELECT id, code, name_zh, name_en, category, description, base_price_cents "
                    "FROM service_modules WHERE is_active=1 ORDER BY sort_order")
        rows = cur.fetchall()
    for r in rows:
        r["base_price"] = (r["base_price_cents"] or 0) / 100
        r.pop("base_price_cents", None)
    return {"modules": rows}


# ── 合同 CRUD ───────────────────────────────────────────────────

class ContractItemReq(BaseModel):
    module_code: str
    amount: float
    notes: str | None = None


class ContractCreate(BaseModel):
    student_member_id: str
    lead_id: str | None = None
    items: list[ContractItemReq] = Field(..., min_length=1)
    signed_date: str | None = None
    service_start: str | None = None
    service_end: str | None = None
    notes: str | None = None
    signed_by_type: str = "student"  # student/parent
    signed_by_member_id: str | None = None


@router.post("")
def create_contract(req: ContractCreate, user: dict = Depends(auth.require_staff),
                    org_id: str = Depends(get_org_id)):
    # 校验学生
    with db_cursor() as cur:
        cur.execute("SELECT id FROM members WHERE id=%s AND org_id=%s AND role='student'",
                    (req.student_member_id, org_id))
        if not cur.fetchone():
            raise HTTPException(400, "学生不存在")
        cur.execute("SELECT code FROM service_modules WHERE is_active=1")
        valid = {r["code"] for r in cur.fetchall()}
    for it in req.items:
        if it.module_code not in valid:
            raise HTTPException(400, f"无效服务模块：{it.module_code}")

    # 校验代签
    if req.signed_by_type == "parent":
        if not req.signed_by_member_id:
            raise HTTPException(400, "家长代签需提供 signed_by_member_id")
        with db_cursor() as cur:
            cur.execute(
                """SELECT 1 FROM member_relationships
                   WHERE from_member_id=%s AND to_member_id=%s AND org_id=%s""",
                (req.signed_by_member_id, req.student_member_id, org_id))
            if not cur.fetchone():
                raise HTTPException(400, "代签人不是该学生的关联家长")

    cid = new_id()
    cno = new_order_no("CT")
    total = round(sum(it.amount for it in req.items), 2)
    with db_transaction() as cur:
        cur.execute(
            """INSERT INTO contracts
               (id, org_id, contract_no, student_member_id, lead_id, modules, total_amount,
                signed_date, service_start, service_end, status, notes, created_by,
                signed_by_type, signed_by_member_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s,%s,%s,%s)""",
            (cid, org_id, cno, req.student_member_id, req.lead_id,
             json.dumps([it.module_code for it in req.items]), total,
             req.signed_date, req.service_start, req.service_end, req.notes,
             user.get("member_id"), req.signed_by_type, req.signed_by_member_id))
        for i, it in enumerate(req.items):
            cur.execute(
                """INSERT INTO contract_items
                   (id, org_id, contract_id, module_code, amount, status, notes, sort_order)
                   VALUES (%s,%s,%s,%s,%s,'pending',%s,%s)""",
                (new_id(), org_id, cid, it.module_code, it.amount, it.notes, i))
        cur.execute(
            """INSERT INTO audit_log (id, org_id, actor_member_id, action, target_type, target_id, detail)
               VALUES (%s,%s,%s,'contract_sign','contract',%s,%s)""",
            (new_id(), org_id, user.get("member_id"), cid,
             json.dumps({"contract_no": cno, "amount": total, "items": len(req.items)})))
    return {"contract_id": cid, "contract_no": cno, "total_amount": total,
            "items": [it.model_dump() for it in req.items]}


# ── 列表 / 详情 ────────────────────────────────────────────────

@router.get("")
def list_contracts(user: dict = Depends(auth.get_current_user), org_id: str = Depends(get_org_id),
                   status: str | None = None, student_id: str | None = None,
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    where = ["c.org_id=%s"]
    params = [org_id]
    if user["role"] == auth.ROLE_STUDENT:
        where.append("c.student_member_id=%s")
        params.append(user.get("member_id"))
    elif user["role"] == auth.ROLE_PARENT:
        where.append("""c.student_member_id IN (SELECT to_member_id FROM member_relationships
                        WHERE from_member_id=%s AND org_id=%s)""")
        params.extend([user.get("member_id"), org_id])
    elif student_id:
        where.append("c.student_member_id=%s")
        params.append(student_id)
    if status:
        where.append("c.status=%s")
        params.append(status)
    sql_where = " AND ".join(where)
    offset = (page - 1) * page_size
    with db_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM contracts c WHERE {sql_where}", params)
        total = cur.fetchone()["c"]
        cur.execute(
            f"""SELECT c.*, m.name AS student_name, sb.name AS signed_by_name,
                  (SELECT COALESCE(SUM(amount),0) FROM contract_payments p WHERE p.contract_id=c.id) AS paid_amount
                FROM contracts c
                LEFT JOIN members m ON m.id=c.student_member_id
                LEFT JOIN members sb ON sb.id=c.signed_by_member_id
                WHERE {sql_where}
                ORDER BY FIELD(c.status,'active','completed','terminated'), c.signed_date DESC
                LIMIT %s OFFSET %s""", params + [page_size, offset])
        rows = [_row(r) for r in cur.fetchall()]
        # 附加每个合同的 items
        if rows:
            cids = [r["id"] for r in rows]
            fmt = ",".join(["%s"] * len(cids))
            cur.execute(
                f"""SELECT id, contract_id, module_code, amount, status,
                          deliverable_id, refund_amount, started_at, completed_at
                   FROM contract_items WHERE contract_id IN ({fmt})
                   ORDER BY sort_order""", cids)
            items_by_cid = {}
            for it in cur.fetchall():
                items_by_cid.setdefault(it["contract_id"], []).append(_row(it))
            for r in rows:
                r["items"] = items_by_cid.get(r["id"], [])
    return {"total": total, "items": rows}


@router.get("/{contract_id}")
def contract_detail(contract_id: str, user: dict = Depends(auth.get_current_user),
                    org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute(
            """SELECT c.*, m.name AS student_name, sb.name AS signed_by_name
               FROM contracts c
               LEFT JOIN members m ON m.id=c.student_member_id
               LEFT JOIN members sb ON sb.id=c.signed_by_member_id
               WHERE c.id=%s AND c.org_id=%s""", (contract_id, org_id))
        c = cur.fetchone()
        if not c: raise HTTPException(404, "合同不存在")
        if user["role"] in (auth.ROLE_STUDENT, auth.ROLE_PARENT):
            if c["student_member_id"] != user.get("member_id"):
                cur.execute(
                    "SELECT 1 FROM member_relationships WHERE from_member_id=%s AND to_member_id=%s",
                    (user.get("member_id"), c["student_member_id"]))
                if not cur.fetchone():
                    raise HTTPException(403, "无权查看")
        cur.execute(
            """SELECT id, contract_id, module_code, amount, status,
                      deliverable_id, refund_amount, started_at, completed_at, notes
               FROM contract_items WHERE contract_id=%s ORDER BY sort_order""", (contract_id,))
        items = [_row(i) for i in cur.fetchall()]
        cur.execute(
            "SELECT * FROM contract_payments WHERE contract_id=%s ORDER BY paid_at DESC, created_at DESC",
            (contract_id,))
        payments = [_row(p) for p in cur.fetchall()]
    out = _row(c)
    out["items"] = items
    out["payments"] = payments
    out["paid_amount"] = sum(p["amount"] for p in payments)
    out["refunded_amount"] = sum(i["refund_amount"] or 0 for i in items)
    out["remaining_amount"] = round(out["total_amount"] - out["paid_amount"] + out["refunded_amount"], 2)
    return out


class ContractStatusReq(BaseModel):
    status: str


@router.post("/{contract_id}/status")
def update_status(contract_id: str, req: ContractStatusReq,
                  user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    if req.status not in ("active", "completed", "terminated"):
        raise HTTPException(400, "无效状态")
    with db_transaction() as cur:
        cur.execute("UPDATE contracts SET status=%s WHERE id=%s AND org_id=%s",
                    (req.status, contract_id, org_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "合同不存在")
        if req.status == "terminated":
            cur.execute(
                "UPDATE contract_items SET status='cancelled' WHERE contract_id=%s AND status NOT IN ('completed','refunded')",
                (contract_id,))
    return {"ok": True}


# ── 合同项状态（开始/交付/完成） ─────────────────────────────

class ItemStatusReq(BaseModel):
    status: str  # pending/in_progress/delivered/completed
    deliverable_id: str | None = None


@router.post("/{contract_id}/items/{iid}/status")
def set_item_status(contract_id: str, iid: str, req: ItemStatusReq,
                    user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    if req.status not in ITEM_STATUSES:
        raise HTTPException(400, "无效状态")
    with db_cursor() as cur:
        cur.execute("SELECT * FROM contract_items WHERE id=%s AND contract_id=%s AND org_id=%s",
                    (iid, contract_id, org_id))
        if not cur.fetchone():
            raise HTTPException(404, "合同项不存在")
        now = datetime.utcnow()
        started = "started_at=COALESCE(started_at,%s)" if req.status == "in_progress" else None
        delivered = "delivered_at=COALESCE(delivered_at,%s)" if req.status == "delivered" else None
        completed = "completed_at=COALESCE(completed_at,%s)" if req.status == "completed" else None
        sets = ["status=%s", "deliverable_id=COALESCE(%s,deliverable_id)"]
        params = [req.status, req.deliverable_id]
        if started: sets.append(started); params.append(now)
        if delivered: sets.append(delivered); params.append(now)
        if completed: sets.append(completed); params.append(now)
        params.extend([iid, contract_id, org_id])
        cur.execute(f"UPDATE contract_items SET {', '.join(sets)} WHERE id=%s AND contract_id=%s AND org_id=%s", params)
    return {"ok": True}


# ── 退费 ──────────────────────────────────────────────────────

class RefundReq(BaseModel):
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=5)


@router.post("/{contract_id}/items/{iid}/refund")
def refund_item(contract_id: str, iid: str, req: RefundReq,
                user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    with db_transaction() as cur:
        cur.execute("SELECT * FROM contract_items WHERE id=%s AND contract_id=%s AND org_id=%s",
                    (iid, contract_id, org_id))
        item = cur.fetchone()
        if not item: raise HTTPException(404, "合同项不存在")
        cur.execute(
            "SELECT COALESCE(SUM(amount),0) AS paid FROM contract_payments WHERE contract_id=%s",
            (contract_id,))
        paid = cur.fetchone()["paid"]
        if req.amount > paid:
            raise HTTPException(400, f"退费金额 {req.amount:.2f} 超过已收款 {paid:.2f}")
        now = datetime.utcnow()
        cur.execute(
            "UPDATE contract_items SET status='refunded', refund_amount=%s, refunded_at=%s WHERE id=%s",
            (req.amount, now, iid))
        cur.execute(
            """INSERT INTO audit_log (id, org_id, actor_member_id, action, target_type, target_id, detail)
               VALUES (%s,%s,%s,'item_refund','contract_item',%s,%s)""",
            (new_id(), org_id, user.get("member_id"), iid,
             json.dumps({"amount": req.amount, "reason": req.reason, "contract_id": contract_id})))
    return {"ok": True, "refunded": req.amount}


# ── 续约 ──────────────────────────────────────────────────────

class RenewReq(BaseModel):
    extend_months: int = Field(..., ge=1, le=36)
    new_items: list[ContractItemReq] = Field(..., min_length=1)
    signed_by_type: str = "student"
    signed_by_member_id: str | None = None


@router.post("/{contract_id}/renew")
def renew_contract(contract_id: str, req: RenewReq,
                   user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM contracts WHERE id=%s AND org_id=%s", (contract_id, org_id))
        old = cur.fetchone()
        if not old: raise HTTPException(404, "原合同不存在")
        cur.execute("SELECT code FROM service_modules WHERE is_active=1")
        valid = {r["code"] for r in cur.fetchall()}
    for it in req.new_items:
        if it.module_code not in valid:
            raise HTTPException(400, f"无效服务模块：{it.module_code}")
    cid = new_id()
    # 编号后缀 R1/R2
    cur = None
    with db_cursor() as cur2:
        cur2.execute(
            "SELECT contract_no FROM contracts WHERE contract_no LIKE %s ORDER BY contract_no DESC LIMIT 1",
            (old["contract_no"] + "_R%",))
        last = cur2.fetchone()
    suffix = "_R1"
    if last:
        try: suffix = f"_R{int(last['contract_no'].split('_R')[-1]) + 1}"
        except: pass
    new_no = old["contract_no"] + suffix
    total = round(sum(it.amount for it in req.new_items), 2)
    today = date.today()
    if old.get("service_end") and old["service_end"] > today:
        new_start = old["service_end"]
    else:
        new_start = today
    new_end = (new_start + timedelta(days=30*req.extend_months)).isoformat()
    with db_transaction() as cur:
        cur.execute(
            """INSERT INTO contracts
               (id, org_id, contract_no, student_member_id, lead_id, modules, total_amount,
                signed_date, service_start, service_end, status, notes, created_by,
                signed_by_type, signed_by_member_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',CONCAT('续约自 ',%s),%s,%s,%s)""",
            (cid, org_id, new_no, old["student_member_id"], old.get("lead_id"),
             json.dumps([it.module_code for it in req.new_items]), total,
             today, new_start, new_end, old["contract_no"],
             user.get("member_id"), req.signed_by_type, req.signed_by_member_id))
        for i, it in enumerate(req.new_items):
            cur.execute(
                """INSERT INTO contract_items
                   (id, org_id, contract_id, module_code, amount, status, notes, sort_order)
                   VALUES (%s,%s,%s,%s,%s,'pending',%s,%s)""",
                (new_id(), org_id, cid, it.module_code, it.amount, it.notes, i))
        cur.execute(
            """INSERT INTO audit_log (id, org_id, actor_member_id, action, target_type, target_id, detail)
               VALUES (%s,%s,%s,'contract_renew','contract',%s,%s)""",
            (new_id(), org_id, user.get("member_id"), cid,
             json.dumps({"from_contract": contract_id, "months": req.extend_months})))
    return {"new_contract_id": cid, "new_contract_no": new_no, "total_amount": total}


# ── 收款登记 ─────────────────────────────────────────────────

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
        if not cur.fetchone(): raise HTTPException(404, "合同不存在")
        pid = new_id()
        cur.execute(
            """INSERT INTO contract_payments
               (id, org_id, contract_id, amount, pay_type, pay_method, paid_at, note, recorded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (pid, org_id, contract_id, req.amount, req.pay_type, req.pay_method,
             req.paid_at, req.note, user.get("member_id")))
    return {"payment_id": pid}
