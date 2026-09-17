# -*- coding: utf-8 -*-
"""智能评估配额 (SaaS 计费核心)

免费套餐:
  - 年度总量 120 次/年
  - 月度上限 10 次/月

购买套餐 (quota_orders):
  - payg       按量      ¥1/次    (pack_calls=1,  price=100)
  - quota_30   30次包    ¥20      (pack_calls=30, price=2000)
  - quota_100  100次包   ¥60      (pack_calls=100, price=6000)

用量优先级: 购买的包先扣 (按购入时间 FIFO), 免费额度最后扣。
月度上限 10 次只限制免费额度, 不限制已购买额度。
"""

from core.db import db_cursor

# 套餐定义 (SaaS 定价, 单位: 分)
QUOTA_PACKAGES = {
    "payg":       {"label": "按量购买", "calls": 1,   "price": 100,  "desc": "¥1/次"},
    "quota_30":   {"label": "30次包",   "calls": 30,  "price": 2000, "desc": "¥20 (0.67/次)"},
    "quota_100":  {"label": "100次包",  "calls": 100, "price": 6000, "desc": "¥60 (0.60/次)"},
}

FREE_YEARLY = 120
FREE_MONTHLY = 10


def get_usage(org_id: int) -> dict:
    """返回机构当前年度/月度用量 + 剩余 (year, month 都是当前自然年月)"""
    import datetime
    now = datetime.datetime.now()
    year, month = now.year, now.month

    # 免费额度用量 (按 calendar year/month 记录)
    with db_cursor() as c:
        c.execute(
            "SELECT used_year, used_month FROM assessment_quota "
            "WHERE org_id=%s AND year=%s AND month=%s",
            (org_id, year, month),
        )
        row = c.fetchone()
    used_year = (row["used_year"] if row else 0)
    used_month = (row["used_month"] if row else 0)

    # 购买额度: 总量 - 已扣
    with db_cursor() as c:
        c.execute(
            "SELECT COALESCE(SUM(total_calls - used_calls), 0) AS remain "
            "FROM quota_orders WHERE org_id=%s AND status='paid' AND remain_paid_at IS NULL OR "
            "(org_id=%s AND status='paid' AND used_calls < total_calls)",
            (org_id, org_id),
        )
        bought_remain = int((c.fetchone() or {})["remain"] or 0)

    free_yearly_remain = max(0, FREE_YEARLY - used_year)
    free_monthly_remain = max(0, FREE_MONTHLY - used_month)
    return {
        "year": year, "month": month,
        "used_year": used_year, "used_month": used_month,
        "free_yearly_total": FREE_YEARLY, "free_monthly_total": FREE_MONTHLY,
        "free_yearly_remain": free_yearly_remain,
        "free_monthly_remain": free_monthly_remain,
        "bought_remain": bought_remain,
        "total_remain": free_yearly_remain + bought_remain,
    }


def check_and_consume(org_id: int) -> dict:
    """检查配额并扣 1 次。返回 {"ok": bool, "reason": str, ...usage}

    扣减顺序:
      1. 已购买额度 (FIFO: 最先购买的包先扣, 月度上限不适用)
      2. 免费额度 (受月度 10 次上限 + 年度 120 次上限)
    """
    import datetime
    now = datetime.datetime.now()
    year, month = now.year, now.month

    # 1. 先扣已购买 (FIFO)
    with db_cursor() as c:
        c.execute(
            "SELECT id, total_calls, used_calls FROM quota_orders "
            "WHERE org_id=%s AND status='paid' AND used_calls < total_calls "
            "ORDER BY paid_at ASC LIMIT 1 FOR UPDATE",
            (org_id,),
        )
        pack = c.fetchone()
        if pack:
            c.execute(
                "UPDATE quota_orders SET used_calls = used_calls + 1 WHERE id=%s",
                (pack["id"],),
            )
            c.execute(
                "INSERT INTO assessment_quota (org_id, year, month, used_year, used_month) "
                "VALUES (%s,%s,%s,0,1) "
                "ON DUPLICATE KEY UPDATE used_year = used_year, used_month = used_month + 1",
                (org_id, year, month),
            )
            return {"ok": True, "source": "bought", **get_usage(org_id)}

    # 2. 免费额度 (年 120 / 月 10)
    usage = get_usage(org_id)
    if usage["used_year"] >= FREE_YEARLY:
        return {"ok": False, "reason": "annual_limit",
                "msg": f"本年度免费评估额度已用完 ({FREE_YEARLY} 次), 请购买加油包", **usage}
    if usage["used_month"] >= FREE_MONTHLY:
        return {"ok": False, "reason": "monthly_limit",
                "msg": f"本月评估次数已达上限 ({FREE_MONTHLY} 次/月), 可购买加油包继续使用", **usage}

    with db_cursor() as c:
        c.execute(
            "INSERT INTO assessment_quota (org_id, year, month, used_year, used_month) "
            "VALUES (%s,%s,%s,1,1) "
            "ON DUPLICATE KEY UPDATE used_year = used_year + 1, used_month = used_month + 1",
            (org_id, year, month),
        )
    return {"ok": True, "source": "free", **get_usage(org_id)}
