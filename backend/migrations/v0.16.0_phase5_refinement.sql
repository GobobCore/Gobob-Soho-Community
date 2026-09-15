-- ============================================================================
-- Gobob SOHO v0.16.0 — Phase 5 业务细化迁移
-- 2026-09-15
--
-- 涵盖（设计文档：docs/PHASE5_BUSINESS_REFINEMENT.md）：
--   A. 合同明细：contract_items 表（核心新增）；contracts 加 signed_by 列
--   B. 任务依赖：task_dependencies 表
--   C. 交付物多版本：deliverable_versions + deliverable_comments 表
--   D. 家长多对多：member_relationships.rel_type 改枚举
--   E. 流失原因：leads.lost_reason 列（结构化枚举）
--   F. 源 ROI：lead_sources 表（机构自定义来源）
--   G. 机构配置：orgs.settings JSON 列（回收天数等）
--
-- 全部幂等（CREATE TABLE IF NOT EXISTS / IF NOT EXISTS for ADD COLUMN）。
-- 拆合同 JSON 的脚本在 backend/scripts/phase5_migrate_data.py。
-- ============================================================================

-- ── G. 机构配置 ───────────────────────────────────────────────────
-- 既存 schema.sql 是用 CREATE TABLE IF NOT EXISTS 写的 orgs,
-- v0.16 之前没 settings 列. 这里加,幂等.
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'orgs' AND column_name = 'settings'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE orgs ADD COLUMN settings JSON DEFAULT NULL",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── F. 来源 ROI ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lead_sources (
    id          VARCHAR(64) PRIMARY KEY,
    org_id      VARCHAR(64) NOT NULL,
    name        VARCHAR(100) NOT NULL,
    category    VARCHAR(50) DEFAULT 'online' COMMENT 'online/referral/event/ads/offline',
    cost_cents  BIGINT DEFAULT 0 COMMENT '每线索获客成本（分）',
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_name (org_id, name),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 预置来源（与 leads.source 既有枚举对齐）
INSERT IGNORE INTO lead_sources (id, org_id, name, category) VALUES
  (CONCAT('src_assessment_', UUID_SHORT()), NULL, '智能评估', 'online'),
  (CONCAT('src_online_',     UUID_SHORT()), NULL, '线上咨询', 'online'),
  (CONCAT('src_referral_',   UUID_SHORT()), NULL, '转介绍', 'referral'),
  (CONCAT('src_event_',      UUID_SHORT()), NULL, '讲座', 'event'),
  (CONCAT('src_ads_',         UUID_SHORT()), NULL, '广告', 'ads'),
  (CONCAT('src_offline_',    UUID_SHORT()), NULL, '地推', 'offline'),
  (CONCAT('src_other_',      UUID_SHORT()), NULL, '其他', 'online');
-- 注：org_id 留 NULL 视为全局预置（所有机构可引用）；owner 可在机构设置里 fork/重命名

-- ── E. 流失原因 ───────────────────────────────────────────────────
-- 加 lost_reason 列（不破坏旧 status='lost' 记录）
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'leads' AND column_name = 'lost_reason'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE leads ADD COLUMN lost_reason VARCHAR(50) DEFAULT NULL AFTER status,
                      ADD COLUMN lost_detail  VARCHAR(500) DEFAULT NULL AFTER lost_reason",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── A. 合同明细：contract_items 表 ───────────────────────────────
CREATE TABLE IF NOT EXISTS contract_items (
    id              VARCHAR(64) PRIMARY KEY,
    org_id          VARCHAR(64) NOT NULL,
    contract_id     VARCHAR(64) NOT NULL,
    module_code     VARCHAR(64) NOT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    status          ENUM('pending','in_progress','delivered','completed','cancelled','refunded') DEFAULT 'pending',
    deliverable_id  VARCHAR(64) DEFAULT NULL,
    started_at      DATETIME DEFAULT NULL,
    delivered_at    DATETIME DEFAULT NULL,
    completed_at    DATETIME DEFAULT NULL,
    refund_amount   DECIMAL(12,2) DEFAULT 0,
    refunded_at     DATETIME DEFAULT NULL,
    notes           TEXT,
    sort_order      INT DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_contract (org_id, contract_id),
    INDEX idx_status (status),
    INDEX idx_deliverable (deliverable_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- contracts 加 signed_by 列
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'contracts' AND column_name = 'signed_by_type'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE contracts ADD COLUMN signed_by_type ENUM('student','parent') DEFAULT 'student' AFTER created_by,
                      ADD COLUMN signed_by_member_id VARCHAR(64) DEFAULT NULL AFTER signed_by_type",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── B. 任务依赖 ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_dependencies (
    id          VARCHAR(64) PRIMARY KEY,
    org_id      VARCHAR(64) NOT NULL,
    task_id     VARCHAR(64) NOT NULL,
    depends_on  VARCHAR(64) NOT NULL,
    type        ENUM('hard','soft') DEFAULT 'hard',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task (task_id),
    INDEX idx_dep (depends_on),
    UNIQUE KEY uk_pair (task_id, depends_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- task_template_items 加 depends_on_item_key（按模板内 title 引用，避免跨实例错乱）
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'task_template_items' AND column_name = 'depends_on_item_key'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE task_template_items ADD COLUMN depends_on_item_key VARCHAR(200) DEFAULT NULL AFTER offset_days",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── C. 交付物多版本 ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deliverable_versions (
    id              VARCHAR(64) PRIMARY KEY,
    org_id          VARCHAR(64) NOT NULL,
    deliverable_id  VARCHAR(64) NOT NULL,
    version         INT NOT NULL,
    content         TEXT,
    file_url        VARCHAR(512),
    submitted_by    VARCHAR(64),
    submitted_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_deliv (deliverable_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS deliverable_comments (
    id          VARCHAR(64) PRIMARY KEY,
    org_id      VARCHAR(64) NOT NULL,
    version_id  VARCHAR(64) NOT NULL,
    reviewer_member_id VARCHAR(64),
    reviewer_name VARCHAR(100),
    content     TEXT NOT NULL,
    decision    ENUM('approve','reject','comment') DEFAULT 'comment',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_version (version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- deliverables 加 current_version 指向最新版本
SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'deliverables' AND column_name = 'current_version_id'
);
SET @ddl := IF(@col_exists = 0,
  "ALTER TABLE deliverables ADD COLUMN current_version_id VARCHAR(64) DEFAULT NULL",
  "SELECT 1");
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ── D. 家长多对多：member_relationships.rel_type 改枚举 ──────────
-- 先把 VARCHAR(50) 改成更宽的 VARCHAR(64) 兼容旧值
ALTER TABLE member_relationships MODIFY COLUMN rel_type VARCHAR(64) DEFAULT 'guardian';
-- 注：不强行改成 ENUM（迁移更稳；后端用 EnumLiteral 校验；旧值 'parent_of' 在 phase5_migrate_data.py 归一为 'guardian'）

-- ── 后端 cron 配置项：orgs.settings JSON 用法约定 ────────────────
-- settings 形如：
-- {
--   "lead_recycle_days": 7,         -- N 天无跟进自动回公海
--   "lead_aging_warn_days": 3,      -- N 天未跟进开始告警
--   "contract_renewal_warn_days": 30  -- 合同到期前 N 天提醒
-- }
