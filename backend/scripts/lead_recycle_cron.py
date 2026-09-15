#!/usr/bin/env python3
"""
lead_recycle_cron.py — 线索公海自动回收（30min 跑一次）

行为：
- 读 orgs.settings（JSON）拿 lead_recycle_days（默认 7）
- 找"超过 N 天 last_contact_at（或 created_at，从未跟进）"且 status NOT IN ('converted','lost')
  且 is_recycled=0 的线索 → assigned_advisor_id=NULL, is_recycled=1, status='recycled'
- 写 lead_activities 记录（actor_name='系统自动回收'）
- 写 notifications 给"原归属顾问"提醒（'你有一条线索被自动回收到公海：<原因>'）

用法：SOHO_MYSQL_HOST=... python3 lead_recycle_cron.py
systemd timer 示例（30min）：
  [Unit]
  Description=Gobob SOHO lead recycle cron
  [Service]
  ExecStart=/usr/bin/python3 /path/to/lead_recycle_cron.py
  Environment=SOHO_MYSQL_HOST=...
"""

import json
import os
import sys
from datetime import datetime, timedelta

import pymysql
from pymysql.cursors import DictCursor


def get_conn():
    return pymysql.connect(
        host=os.environ.get("SOHO_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("SOHO_MYSQL_PORT", "3306")),
        user=os.environ.get("SOHO_MYSQL_USER", "soho"),
        password=os.environ.get("SOHO_MYSQL_PASS", ""),
        database=os.environ.get("SOHO_MYSQL_DB", "gobob_soho"),
        charset="utf8mb4",
        autocommit=True,
        cursorclass=DictCursor,
    )


def org_settings(conn, org_id):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT settings FROM orgs WHERE id=%s", (org_id,))
            row = cur.fetchone()
        if row and row.get("settings"):
            try:
                return json.loads(row["settings"]) if isinstance(row["settings"], str) else row["settings"]
            except: pass
    except: pass
    return {}


def recycle_one_org(conn, org_id, default_days=7):
    s = org_settings(conn, org_id)
    days = int(s.get("lead_recycle_days", default_days))
    warn_days = int(s.get("lead_aging_warn_days", 3))
    warn_cutoff = datetime.utcnow() - timedelta(days=warn_days)
    recycle_cutoff = datetime.utcnow() - timedelta(days=days)
    recycled = 0
    warned = 0

    with conn.cursor() as cur:
        # 先发"快到期"提醒（warn_days ≤ N ≤ days）—— 不在 schema 加字段，用 status='new' + notification 提示
        cur.execute(
            """SELECT lead_id, student_name, assigned_advisor_id, last_contact_at, created_at
               FROM leads
               WHERE org_id=%s AND is_recycled=0
                 AND status NOT IN ('converted','lost','recycled')
                 AND assigned_advisor_id IS NOT NULL
                 AND COALESCE(last_contact_at, created_at) < %s
                 AND COALESCE(last_contact_at, created_at) >= %s""",
            (org_id, recycle_cutoff, warn_cutoff))
        warns = cur.fetchall()
        for w in warns:
            # 避免重复提醒：检查今日是否已发过
            cur.execute(
                """SELECT 1 FROM notifications
                   WHERE org_id=%s AND member_id=%s AND type='recycle_warn'
                     AND DATE(created_at)=CURDATE()
                     AND content LIKE %s""",
                (org_id, w["assigned_advisor_id"], f"%{w['lead_id']}%"))
            if not cur.fetchone():
                cur.execute(
                    """INSERT INTO notifications
                       (id, org_id, member_id, title, content, type)
                       VALUES (%s,%s,%s,%s,%s,'recycle_warn')""",
                    (f"ntf_{datetime.now().timestamp()}_{w['lead_id'][-6:]}",
                     org_id, w["assigned_advisor_id"],
                     f"线索 {w['student_name']} 即将被自动回收",
                     f"该线索已 {warn_days} 天未跟进，将在 {days} 天后自动回收到公海，请尽快跟进。",
                     ))
                warned += 1

        # 实际回收
        cur.execute(
            """SELECT lead_id, student_name, assigned_advisor_id
               FROM leads
               WHERE org_id=%s AND is_recycled=0
                 AND status NOT IN ('converted','lost','recycled')
                 AND assigned_advisor_id IS NOT NULL
                 AND COALESCE(last_contact_at, created_at) < %s""",
            (org_id, recycle_cutoff))
        for r in cur.fetchall():
            cur.execute(
                "UPDATE leads SET assigned_advisor_id=NULL, is_recycled=1, status='recycled' WHERE lead_id=%s",
                (r["lead_id"],))
            cur.execute(
                """INSERT INTO lead_activities
                   (activity_id, org_id, lead_id, activity_type, subject, actor_name)
                   VALUES (%s,%s,%s,'status_change',%s,'系统自动回收')""",
                (f"act_{datetime.now().timestamp()}_{r['lead_id'][-6:]}",
                 org_id, r["lead_id"],
                 f"{days} 天未跟进，自动回收到公海"))
            cur.execute(
                """INSERT INTO notifications
                   (id, org_id, member_id, title, content, type)
                   VALUES (%s,%s,%s,%s,%s,'recycle')""",
                (f"ntf_rc_{datetime.now().timestamp()}_{r['lead_id'][-6:]}",
                 org_id, r["assigned_advisor_id"],
                 f"线索 {r['student_name']} 已被自动回收到公海",
                 f"该线索超过 {days} 天未跟进，已自动回收。重新认领：线索池 → 看板 → 公海列 → 认领"))
            recycled += 1
    return recycled, warned


def main():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM orgs")
        orgs = cur.fetchall()
    total_r, total_w = 0, 0
    for org in orgs:
        r, w = recycle_one_org(conn, org["id"])
        if r or w:
            print(f"[{org['name']}] 回收 {r} 条 / 提醒 {w} 条")
        total_r += r; total_w += w
    print(f"== 总计：回收 {total_r} 提醒 {total_w} ==")
    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"✗ cron failed: {e}", file=sys.stderr)
        sys.exit(1)
