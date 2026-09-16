-- ============================================================================
-- Gobob SOHO v0.17.0 — SaaS 运营后台迁移
-- 2026-09-16
--
-- 背景: SOHO 拆成 2 个运营产品
--   1. SaaS 版 (官方托管, 多机构): 1-2 协作账号免费, >=3 每个 ¥1000/年
--      例: 5 账号 ¥3000/年, 10 账号 ¥8000/年. Gobob Data API 含在服务费里不限次.
--   2. 开源版 (自托管): 软件免费, 单独按次买 Gobob Data API (¥1/次, 后做).
--
-- 本 migration 支持 SaaS 运营后台 (soho-ops :19004):
--   A. orgs 加订阅字段: plan_status / seats_paid / paid_until / contact / disabled
--   B. 新表 saas_invoices: 收费/账单流水 (台账, 不接在线支付)
--   C. 新表 saas_api_usage: SaaS 机构调 Gobob Data API 的按日聚合 (成本核算 + 防滥用)
--   D. 新表 saas_ops_admins: 运营后台登录账号 (跟机构业务账号 accounts 完全隔离)
--
-- 全部幂等.
-- ============================================================================

-- ── A. orgs 加订阅字段 ───────────────────────────────────────────
-- plan_status: free(<=2 协作账号) / paid(付费) / trial(试用) / suspended(欠费停用)
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'plan_status'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE orgs ADD COLUMN plan_status ENUM('free','trial','paid','suspended') NOT NULL DEFAULT 'free' AFTER settings",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- seats_paid: 已付费的协作账号数 (owner+advisor, 不含 student/parent). 0=纯免费版
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'seats_paid'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE orgs ADD COLUMN seats_paid INT NOT NULL DEFAULT 0 AFTER plan_status",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- paid_until: 付费有效期 (NULL=无付费/免费版)
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'paid_until'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE orgs ADD COLUMN paid_until DATE DEFAULT NULL AFTER seats_paid",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- contact_name / contact_phone / contact_email: 机构对接人 (开账单/催费用)
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'contact_name'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE orgs ADD COLUMN contact_name VARCHAR(100) DEFAULT NULL AFTER paid_until,
                          ADD COLUMN contact_phone VARCHAR(50) DEFAULT NULL AFTER contact_name,
                          ADD COLUMN contact_email VARCHAR(200) DEFAULT NULL AFTER contact_phone",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- disabled: 运营停用 (欠费/违规), 比 plan_status=suspended 更硬 — 停用后全机构登不进
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'disabled'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE orgs ADD COLUMN disabled TINYINT(1) NOT NULL DEFAULT 0 AFTER contact_email",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── B. 收费/账单流水 (台账, 不接在线支付) ─────────────────────────
CREATE TABLE IF NOT EXISTS saas_invoices (
  id            VARCHAR(64) PRIMARY KEY,
  org_id        VARCHAR(64) NOT NULL,
  invoice_no    VARCHAR(50) NOT NULL COMMENT 'SO2026xxx 可读单号',
  seats         INT NOT NULL COMMENT '本次付费账号数',
  unit_price    DECIMAL(10,2) NOT NULL DEFAULT 1000.00 COMMENT '单价 ¥/账号/年',
  amount        DECIMAL(12,2) NOT NULL COMMENT '应付金额 (seats * unit_price, 可有折扣)',
  period_start  DATE NOT NULL COMMENT '服务期起',
  period_end    DATE NOT NULL COMMENT '服务期止',
  status        ENUM('pending','paid','void') NOT NULL DEFAULT 'pending' COMMENT 'pending=待收 paid=已收 void=作废',
  paid_at       DATETIME DEFAULT NULL,
  payment_method VARCHAR(50) DEFAULT NULL COMMENT '线下转账/支付宝/微信 (台账手填)',
  note          VARCHAR(500) DEFAULT NULL,
  created_by    VARCHAR(64) DEFAULT NULL COMMENT '操作运营 (saas_ops_admins.id)',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_org (org_id),
  INDEX idx_status (status),
  INDEX idx_period_end (period_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── C. SaaS 机构 Gobob Data API 用量 (按日聚合) ──────────────────
-- SaaS 版机构调 Gobob 走官方主 Key (不限次, 成本运营方扛), 但要能看到谁调得多.
-- 原始明细在 Gobob 主站 api_key_logs (主 Key 的), 这里按 org+day+endpoint 聚合回写,
-- 用于运营后台「用量」页 + 成本核算 + 异常告警.
CREATE TABLE IF NOT EXISTS saas_api_usage (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  org_id        VARCHAR(64) NOT NULL,
  usage_date    DATE NOT NULL,
  endpoint      VARCHAR(100) NOT NULL COMMENT '如 /api/smb/v1/match',
  calls         INT NOT NULL DEFAULT 0,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_org_date_endpoint (org_id, usage_date, endpoint),
  INDEX idx_org_date (org_id, usage_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── D. 运营后台登录账号 (跟机构业务账号完全隔离) ──────────────────
-- SaaS 运营后台只有 Gobob 运营方 (小Z 等) 能登, 不是任何机构的 owner.
-- 独立表, 不复用 accounts/members, 避免跟机构业务身份混淆.
CREATE TABLE IF NOT EXISTS saas_ops_admins (
  id            VARCHAR(64) PRIMARY KEY,
  username      VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  name          VARCHAR(100) DEFAULT NULL,
  is_super      TINYINT(1) NOT NULL DEFAULT 1 COMMENT '预留: 未来区分超管/只读运营',
  status        ENUM('active','disabled') NOT NULL DEFAULT 'active',
  last_login_at DATETIME DEFAULT NULL,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
