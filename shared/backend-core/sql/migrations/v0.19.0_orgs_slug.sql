-- =====================================================
-- Gobob SOHO v0.19.0 — orgs 加 slug 列 (多机构 SaaS 路由)
-- 2026-09-16
--
-- SaaS 版多机构识别: portal ?org=demo-studio → 后端按 slug 查 org_id
-- =====================================================

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'slug'
);
SET @ddl := IF(@col_exists = 0,
  'ALTER TABLE orgs ADD COLUMN slug VARCHAR(64) UNIQUE DEFAULT NULL AFTER name',
  'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
