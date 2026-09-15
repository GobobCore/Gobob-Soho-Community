"""
api/reports.py — 报表端点（Phase 5）

- /api/reports/loss-reasons：流失原因分布
- /api/reports/source-roi：来源 ROI（CPA/转化率）
- /api/reports/collisions：（与 leads.py 重复代理，为了前端用统一 /reports/* 路径）
"""

from fastapi import APIRouter, Depends

from core import auth
from core.database import db_cursor
from core.tenancy import get_org_id

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/loss-reasons")
def loss_reasons(user: dict = Depends(auth.require_staff), org_id: str = Depends(get_org_id)):
    """流失线索：按 lost_reason 分组 + 数量 + 占比。"""
    with db_cursor() as cur:
        cur.execute(
            """SELECT COALESCE(lost_reason,'(未填)') reason, COUNT(*) cnt
               FROM leads WHERE org_id=%s AND status='lost'
               GROUP BY lost_reason ORDER BY cnt DESC""", (org_id,))
        rows = cur.fetchall()
        cur.execute(
            "SELECT COUNT(*) total FROM leads WHERE org_id=%s AND status='lost'", (org_id,))
        total = cur.fetchone()["total"] or 0
    by_reason = [{"reason": r["reason"], "count": r["cnt"],
                  "pct": round(r["cnt"]/total*100, 1) if total else 0} for r in rows]
    return {"total_lost": total, "by_reason": by_reason}


@router.get("/source-roi")
def source_roi(user: dict = Depends(auth.require_owner), org_id: str = Depends(get_org_id)):
    """来源 ROI：每个 source 的 线索数/转化数/签约额/获客成本/CPA/ROI。"""
    with db_cursor() as cur:
        cur.execute(
            """SELECT l.source, COUNT(*) leads, SUM(CASE WHEN l.status='converted' THEN 1 ELSE 0 END) converted
               FROM leads l WHERE l.org_id=%s AND l.is_recycled=0
               GROUP BY l.source""", (org_id,))
        by_src = {r["source"] or "未知": r for r in cur.fetchall()}
        cur.execute(
            """SELECT name, cost_cents FROM lead_sources WHERE org_id=%s AND is_active=1""", (org_id,))
        costs = {r["name"]: r["cost_cents"] for r in cur.fetchall()}
        cur.execute(
            """SELECT l.source, COALESCE(SUM(c.total_amount),0) revenue
               FROM leads l JOIN contracts c ON c.lead_id=l.lead_id
               WHERE l.org_id=%s AND l.is_recycled=0
               GROUP BY l.source""", (org_id,))
        rev = {r["source"] or "未知": float(r["revenue"]) for r in cur.fetchall()}
    items = []
    for src, r in by_src.items():
        cost = float(costs.get(src, 0))
        revenue = rev.get(src, 0.0)
        items.append({
            "source": src,
            "leads": r["leads"],
            "converted": r["converted"],
            "conv_rate": round(r["converted"]/r["leads"]*100, 1) if r["leads"] else 0,
            "revenue_cents": int(revenue*100),
            "cost_cents": int(cost*100),  # 假设 cost 是按线索分摊（元 -> 分）
            "cpa_cents": int(cost*100/r["leads"]) if r["leads"] else 0,
            "roi": "∞" if cost == 0 else round(revenue/cost, 2),
        })
    items.sort(key=lambda x: -x["leads"])
    return {"items": items}
