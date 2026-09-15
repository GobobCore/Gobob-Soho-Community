#!/usr/bin/env python3
"""
Phase 5 数据迁移脚本（幂等可重跑）

做三件事：
1. 拆 contracts.modules JSON → 写 contract_items 行（仅当 contract_items 为空）
2. 归一 member_relationships.rel_type（'parent_of' → 'guardian'）
3. 写预置 lead_sources（让 org_id NULL → 替换为真实 org_id，让 owner 可改）

用法：SOHO_MYSQL_HOST=... python3 phase5_migrate_data.py
"""

import json
import sys
import os
from datetime import datetime

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


def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}")


def migrate_contracts_to_items(conn):
    """拆 contracts.modules JSON → contract_items 行"""
    with conn.cursor() as cur:
        # 已有 items 的合同跳过
        cur.execute("SELECT DISTINCT contract_id FROM contract_items")
        done = {r["contract_id"] for r in cur.fetchall()}
        cur.execute(
            "SELECT id, org_id, modules, total_amount FROM contracts WHERE modules IS NOT NULL AND modules != ''"
        )
        contracts = cur.fetchall()

    migrated = 0
    for c in contracts:
        if c["id"] in done:
            continue
        try:
            modules = json.loads(c["modules"]) if isinstance(c["modules"], str) else c["modules"]
        except Exception:
            log(f"⚠ contract {c['id']} modules JSON 解析失败，跳过")
            continue
        if not modules:
            continue
        # 平分金额：N 个模块均分 total_amount（保留 2 位）
        n = len(modules)
        each = round(float(c["total_amount"]) / n, 2)
        amounts = [each] * n
        # 最后一个吃掉四舍五入差额，确保 sum=total
        amounts[-1] = round(float(c["total_amount"]) - sum(amounts[:-1]), 2)

        with conn.cursor() as cur:
            for i, mod in enumerate(modules):
                cur.execute(
                    """INSERT IGNORE INTO contract_items
                       (id, org_id, contract_id, module_code, amount, status, sort_order)
                       VALUES (%s, %s, %s, %s, %s, 'pending', %s)""",
                    (f"ci_{c['id']}_{i}_{int(datetime.now().timestamp())}",
                     c["org_id"], c["id"], mod, amounts[i], i),
                )
        migrated += 1
    log(f"✓ 拆合同 modules → contract_items: {migrated} 合同（累计已迁 {len(done)+migrated}）")


def migrate_relationships(conn):
    """归一 member_relationships.rel_type"""
    with conn.cursor() as cur:
        cur.execute("SELECT id, rel_type FROM member_relationships WHERE rel_type='parent_of'")
        rows = cur.fetchall()
    if not rows:
        log("✓ member_relationships: 全部已是规范值（无需迁移）")
        return
    with conn.cursor() as cur:
        cur.execute("UPDATE member_relationships SET rel_type='guardian' WHERE rel_type='parent_of'")
    log(f"✓ member_relationships: 'parent_of' → 'guardian'，{cur.rowcount} 条")


def bind_global_lead_sources(conn):
    """把 org_id IS NULL 的 lead_sources（全局预置）复制到每个 org"""
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, category FROM lead_sources WHERE org_id IS NULL")
        globals_ = cur.fetchall()
        cur.execute("SELECT id FROM orgs")
        orgs = cur.fetchall()
    if not globals_:
        log("✓ lead_sources: 预置已绑定（无 NULL org_id）")
        return
    added = 0
    with conn.cursor() as cur:
        for org in orgs:
            for src in globals_:
                cur.execute(
                    """INSERT IGNORE INTO lead_sources (id, org_id, name, category, cost_cents)
                       VALUES (%s, %s, %s, %s, 0)""",
                    (f"src_{org['id']}_{src['id'][-12:]}", org["id"], src["name"], src["category"]),
                )
                added += cur.rowcount
    log(f"✓ lead_sources: 全局预置 × {len(orgs)} 机构，新增 {added} 条机构级副本")


def main():
    try:
        conn = get_conn()
    except Exception as e:
        log(f"✗ 连库失败: {e}")
        sys.exit(1)
    log("Phase 5 数据迁移开始")
    log("─" * 50)
    migrate_contracts_to_items(conn)
    migrate_relationships(conn)
    bind_global_lead_sources(conn)
    log("─" * 50)
    log("Phase 5 数据迁移完成")
    conn.close()


if __name__ == "__main__":
    main()
