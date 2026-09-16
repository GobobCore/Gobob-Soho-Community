-- =====================================================
-- Gobob SOHO v0.20.0 — api_key_* 表 (R-Fix 2026-09-16 拆分补漏)
--
-- 背景: 这 3 个表原本在 backend/migrations/001_api_keys.sql + 002_smb_scopes.sql
--        拆分时 backend/ 被删, migration 漏迁到 shared/backend-core/
-- 新部署跑 schema.sql 没有这些表 → Gobob payment 集成 + api_key 鉴权会崩
-- 修法: 在 shared/backend-core/sql/migrations/ 加这个, 新部署会跑
-- 注: 现有生产 (gobob_soho 库) 已有这些表, 这 migration 幂等
-- =====================================================

-- api_key_scopes: scope 种子
CREATE TABLE IF NOT EXISTS api_key_scopes (
  scope       VARCHAR(64) PRIMARY KEY,
  category    VARCHAR(32) NOT NULL,
  description VARCHAR(255) NOT NULL,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- api_keys: 用户的 API Key
CREATE TABLE IF NOT EXISTS api_keys (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id       VARCHAR(64) NOT NULL,
  name          VARCHAR(128) NOT NULL,
  key_hash      VARCHAR(255) NOT NULL,
  key_prefix    VARCHAR(16) NOT NULL,
  scopes        JSON DEFAULT NULL,
  rate_limit    INT DEFAULT 60,
  expires_at    DATETIME DEFAULT NULL,
  last_used_at  DATETIME DEFAULT NULL,
  last_used_ip  VARCHAR(64) DEFAULT NULL,
  usage_count   BIGINT DEFAULT 0,
  remaining_calls INT DEFAULT NULL COMMENT 'NULL=不限次 (SaaS), 数字=按次剩余',
  status        ENUM('active','revoked') DEFAULT 'active',
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  revoked_at    DATETIME DEFAULT NULL,
  INDEX idx_user (user_id),
  INDEX idx_key_prefix (key_prefix),
  INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- api_key_logs: 调用日志 (R-Feat 2026-09-16 加 org_id)
CREATE TABLE IF NOT EXISTS api_key_logs (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  api_key_id    BIGINT NOT NULL,
  user_id       VARCHAR(64) NOT NULL,
  org_id        VARCHAR(64) DEFAULT NULL,
  method        VARCHAR(10) NOT NULL,
  path          VARCHAR(512) NOT NULL,
  status_code   SMALLINT DEFAULT 200,
  ip            VARCHAR(64) DEFAULT NULL,
  user_agent    VARCHAR(512) DEFAULT NULL,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_key_id (api_key_id),
  INDEX idx_user (user_id),
  INDEX idx_org_created (org_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- api_key_topups: 充值流水 (开源版按次)
CREATE TABLE IF NOT EXISTS api_key_topups (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  api_key_id    BIGINT NOT NULL,
  calls_added   INT NOT NULL,
  amount        DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  payment_method VARCHAR(50) DEFAULT NULL,
  paid_at       DATETIME DEFAULT NULL,
  note          VARCHAR(500) DEFAULT NULL,
  created_by    VARCHAR(64) DEFAULT NULL,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_key (api_key_id),
  INDEX idx_paid (paid_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 种子: 默认 35 个 scope (公共 7 + 用户 18 + admin 4 + smb 6)
INSERT IGNORE INTO api_key_scopes (scope, category, description) VALUES
-- public
('read:schools','public','查询院校库'),
('read:knowledge','public','查询知识库'),
('read:visa','public','查询签证信息'),
('read:rankings','public','查询排名数据'),
('read:topics','public','查询专题内容'),
('read:stories','public','查询留学故事'),
('read:faqs','public','查询常见问题'),
-- user
('read:my:applications','user','查看我的申请'),
('write:my:applications','user','创建/修改申请'),
('read:my:documents','user','查看我的文书'),
('write:my:documents','user','创建/修改文书'),
('read:my:tasks','user','查看我的任务'),
('write:my:tasks','user','创建/修改任务'),
('read:my:interviews','user','查看面试记录'),
('write:my:interviews','user','创建面试记录'),
('read:my:members','user','查看家庭成员'),
('write:my:members','user','管理家庭成员'),
('read:my:visa_checklist','user','查看签证清单'),
('write:my:visa_checklist','user','管理签证清单'),
('read:my:departure_checklist','user','查看行前清单'),
('write:my:departure_checklist','user','管理行前清单'),
('read:my:profile','user','查看个人资料'),
('write:my:profile','user','修改个人资料'),
-- admin
('admin:users','admin','用户管理'),
('admin:content','admin','内容管理'),
('admin:stats','admin','数据统计'),
('admin:api_keys','admin','API Key 管理'),
-- smb (开源版按次, SaaS 运营版也用)
('smb:meta','smb','SOHO: 评估表单元数据'),
('smb:schools','smb','SOHO: 院校库查询'),
('smb:programs','smb','SOHO: 专业/项目查询'),
('smb:rankings','smb','SOHO: 综合与学科排名'),
('smb:match','smb','SOHO: 智能匹配(评估)'),
('smb:cities','smb','SOHO: 城市数据');
