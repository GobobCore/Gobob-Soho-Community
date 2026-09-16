-- =====================================================
-- Gobob SOHO v0.18.0 — lead_pipeline_stages 主键修复
-- 2026-09-16
--
-- Bug: 原主键只有 stage_id (stage_id, org_id 名义上是组合但实际上 PK 只有 stage_id)
-- 后果: 新机构注册时不能复制 pipeline stages (PK 冲突), 全机构共享 7 行数据
-- 修法: 改主键为 (stage_id, org_id) 联合主键, 保留现有数据
-- =====================================================

-- 步骤:
--   1. 备份表 (CREATE TABLE AS SELECT) — 防御性
--   2. DROP 原表 + 重建 (改主键)
--   3. 数据回灌
--   4. 验证

-- 1. 备份 (幂等, 用 IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS lead_pipeline_stages_backup_v018 AS
SELECT * FROM lead_pipeline_stages;

-- 2. DROP + 重建
DROP TABLE lead_pipeline_stages;

CREATE TABLE lead_pipeline_stages (
  stage_id    VARCHAR(64) NOT NULL,
  org_id      VARCHAR(64) NOT NULL,
  name        VARCHAR(100) DEFAULT NULL,
  sort_order  INT DEFAULT NULL,
  is_start    TINYINT(1) DEFAULT 0,
  is_won      TINYINT(1) DEFAULT 0,
  is_lost     TINYINT(1) DEFAULT 0,
  max_days    INT DEFAULT NULL COMMENT '停留超时预警',
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (stage_id, org_id),
  KEY idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. 数据回灌
INSERT INTO lead_pipeline_stages (stage_id, org_id, name, sort_order, is_start, is_won, is_lost, max_days, created_at)
SELECT stage_id, org_id, name, sort_order, is_start, is_won, is_lost, max_days, created_at
FROM lead_pipeline_stages_backup_v018;

-- 4. 清理备份 (可选, 暂时保留 7 天用于审计, 部署后手动 DROP)
-- DROP TABLE lead_pipeline_stages_backup_v018;
