#!/usr/bin/env python3
"""
aggregate_saas_usage.py — saas_api_usage 数据回填
=====================================================

每天从 Gobob 主库 api_key_logs 聚合按 (org_id, usage_date, endpoint) 的调用次数,
UPSERT 到 SOHO 本库的 saas_api_usage (用于 SaaS 运营后台用量页).

数据流: Gobob smb_v1 → api_key_logs(org_id 由 X-Soho-Org-Id 头透传) → SOHO 聚合 → saas_api_usage

用法:
  python3 aggregate_saas_usage.py              # 聚合过去 7 天 (默认)
  python3 aggregate_saas_usage.py --days 30   # 聚合过去 30 天
  python3 aggregate_saas_usage.py --dry-run   # 只统计不写库

环境变量 (需配 systemd Environment):
  GOBOB_DB_HOST   127.0.0.1
  GOBOB_DB_PORT   3306
  GOBOB_DB_USER   root
  GOBOB_DB_PASS   Abccd27366
  GOBOB_DB_NAME   gobob
  SOHO_DB_HOST    127.0.0.1
  SOHO_DB_PORT    3306
  SOHO_DB_USER    root
  SOHO_DB_PASS    Abccd27366
  SOHO_DB_NAME    gobob_soho

R-Feat 2026-09-16: v0.17.0 SaaS 运营后台配套
"""

import argparse
import logging
import os
import sys
from datetime import date, timedelta

import pymysql

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("aggregate_saas_usage")


def get_conn(env_prefix: str) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=os.environ.get(f"{env_prefix}_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get(f"{env_prefix}_DB_PORT", "3306")),
        user=os.environ.get(f"{env_prefix}_DB_USER", "root"),
        password=os.environ.get(f"{env_prefix}_DB_PASS", ""),
        database=os.environ.get(f"{env_prefix}_DB_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def aggregate(days: int, dry_run: bool) -> int:
    gobob = get_conn("GOBOB")
    soho = get_conn("SOHO")
    today = date.today()
    since = today - timedelta(days=days)
    log.info("聚合区间: %s ~ %s", since, today)

    # 从 Gobob 主库聚合
    with gobob.cursor() as cur:
        cur.execute(
            """SELECT org_id, DATE(created_at) AS usage_date, path AS endpoint, COUNT(*) AS calls
               FROM api_key_logs
               WHERE created_at >= %s AND org_id IS NOT NULL AND org_id != ''
               GROUP BY org_id, usage_date, path
               ORDER BY usage_date DESC""",
            (since,),
        )
        rows = cur.fetchall()
    log.info("从 Gobob 主库聚合到 %d 行", len(rows))

    if dry_run:
        log.info("[DRY-RUN] 不写库")
        for r in rows[:10]:
            log.info("  %s", r)
        return len(rows)

    if not rows:
        log.info("无数据, 跳过")
        return 0

    # UPSERT 到 SOHO saas_api_usage
    written = 0
    with soho.cursor() as cur:
        for r in rows:
            cur.execute(
                """INSERT INTO saas_api_usage (org_id, usage_date, endpoint, calls)
                   VALUES (%s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE calls = VALUES(calls), updated_at = NOW()""",
                (r["org_id"], r["usage_date"], r["endpoint"], r["calls"]),
            )
            written += 1
        soho.commit()
    log.info("UPSERT %d 行到 SOHO saas_api_usage", written)
    gobob.close()
    soho.close()
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="聚合过去 N 天 (默认 7)")
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = ap.parse_args()
    try:
        n = aggregate(args.days, args.dry_run)
        log.info("done, %d rows", n)
    except Exception as e:
        log.error("failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
