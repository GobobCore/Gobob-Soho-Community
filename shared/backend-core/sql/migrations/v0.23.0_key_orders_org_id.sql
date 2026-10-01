-- =====================================================
-- Gobob SOHO v0.23.0 — saas_key_orders 加 org_id 列
-- 2026-10-01
--
-- 背景: saas_key_orders 原本只有 org_name VARCHAR(100), 因为订单由运营手工录入
--       (从请求体拿机构名), 历史上一直按名称关联。
--       问题: 机构名不唯一, 且 /api/orgs/me PUT 允许改名 —— 改一次名,
--             该机构所有历史订单在 /api/orgs/me/usage 里就全部查不到 (孤儿化)。
--
-- 本 migration:
--   1. 加 org_id 列 (可空, 保证存量行不失败)
--   2. 按 org_name 回填**唯一匹配**的存量行 (歧义行留 NULL 由人工核对)
--   3. 建索引加速按机构查询
--
-- ⚠ 表存在性防护: saas_key_orders 由 saas/backend/api/saas_admin.py 在运行时
--   DDL 创建, 既不在 shared/sql/schema.sql 里, 也不由社区版创建。因此在
--   纯 SQL 环境 (CI sql-syntax job、社区自建库) 中该表可能不存在 —— 整段
--   必须走动态 SQL 跳过, 否则 ALTER/UPDATE 会直接报错。
--
-- 幂等: 可重复执行。
-- =====================================================

-- ── 表存在则执行主体, 否则整段跳过 ──────────────────────────────────
SET @tbl := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'saas_key_orders'
);

-- 1) 加列
SET @ddl_add := IF(@tbl = 0 OR (
      SELECT COUNT(*) FROM information_schema.columns
      WHERE table_schema = DATABASE()
        AND table_name = 'saas_key_orders'
        AND column_name = 'org_id'
    ) > 0,
  'SELECT 1',
  'ALTER TABLE saas_key_orders
     ADD COLUMN org_id VARCHAR(16) DEFAULT NULL
     COMMENT ''机构 ID (回填自 org_name, 机构改名后不再孤儿)'' AFTER order_no');
PREPARE s1 FROM @ddl_add; EXECUTE s1; DEALLOCATE PREPARE s1;

-- 2) 回填: 只填 org_name 在 orgs 中唯一匹配的行。
--    刻意不做无条件 LEFT JOIN —— 名称重复时一个 org_id 会扇出到多行造成错配。
--    注意 orgs 表的机构名列是 `name`, 不是 org_name。
SET @ddl_fill := IF(@tbl = 0, 'SELECT 1',
  'UPDATE saas_key_orders k
     JOIN (SELECT o.name AS org_name, MIN(o.id) AS org_id
             FROM orgs o GROUP BY o.name HAVING COUNT(*) = 1) om
       ON om.org_name = k.org_name
     SET k.org_id = om.org_id
   WHERE k.org_id IS NULL');
PREPARE s2 FROM @ddl_fill; EXECUTE s2; DEALLOCATE PREPARE s2;

-- 3) 索引
SET @ddl_idx := IF(@tbl = 0 OR (
      SELECT COUNT(*) FROM information_schema.statistics
      WHERE table_schema = DATABASE()
        AND table_name = 'saas_key_orders'
        AND index_name = 'idx_org_id'
    ) > 0,
  'SELECT 1',
  'ALTER TABLE saas_key_orders ADD INDEX idx_org_id (org_id)');
PREPARE s3 FROM @ddl_idx; EXECUTE s3; DEALLOCATE PREPARE s3;
