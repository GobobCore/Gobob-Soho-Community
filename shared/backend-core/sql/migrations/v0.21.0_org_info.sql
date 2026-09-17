-- =====================================================
-- Gobob SOHO v0.21.0 — orgs 表增补机构信息字段 (R-Refactor 2026-09-17 SaaS 设置页)
--
-- 背景: orgs 表原本只有 id/name/gobob_api_key, 机构注册时 owner_name/contact_phone/
--        contact_email 实际存到 members 表 (业务身份), 没存到机构级
-- 新增 6 个列 (description/address/phone/email/website/logo_url) 给机构信息设置:
--   - description: 机构简介
--   - address:     商务地址
--   - phone:       公开联系电话 (与 owner 个人手机分离)
--   - email:       公开联系邮箱 (与 owner 个人邮箱分离)
--   - website:     官方网站 URL
--   - logo_url:    机构 logo URL (覆盖 Gobob 默认 logo)
-- 所有列 nullable — 现有 orgs 行不需要更新数据
-- migration 幂等: 列已存在则不重复添加
-- =====================================================

-- description: 机构简介
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'description'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE orgs ADD COLUMN description TEXT DEFAULT NULL AFTER name',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- address: 商务地址
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'address'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE orgs ADD COLUMN address VARCHAR(500) DEFAULT NULL AFTER description',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- phone: 公开联系电话
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'phone'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE orgs ADD COLUMN phone VARCHAR(50) DEFAULT NULL AFTER address',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- email: 公开联系邮箱
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'email'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE orgs ADD COLUMN email VARCHAR(200) DEFAULT NULL AFTER phone',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- website: 官方网站 URL
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'website'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE orgs ADD COLUMN website VARCHAR(500) DEFAULT NULL AFTER email',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- logo_url: 机构 logo URL (覆盖 Gobob 默认 logo)
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'logo_url'
);
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE orgs ADD COLUMN logo_url VARCHAR(500) DEFAULT NULL AFTER website',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;