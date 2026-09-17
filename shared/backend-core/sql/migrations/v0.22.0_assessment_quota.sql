-- v0.22.0_assessment_quota.sql
-- 智能评估用量配额表 (SaaS 计费基础数据)
-- 免费套餐: 每年 120 次, 每月最多 10 次
-- 套餐: 按量 ¥1/次, 30次包 ¥20, 100次包 ¥60

CREATE TABLE IF NOT EXISTS assessment_quota_usage (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  org_id        CHAR(16) NOT NULL,
  year_month    CHAR(7)  NOT NULL COMMENT 'YYYY-MM, 月度计数窗口',
  used_count    INT      NOT NULL DEFAULT 0 COMMENT '本月已用次数',
  year_used     INT      NOT NULL DEFAULT 0 COMMENT '本年已用次数 (跨月累计行冗余)',
  extra_paid    INT      NOT NULL DEFAULT 0 COMMENT '付费购买的增加量 (年包)',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_org_month (org_id, year_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能评估月度/年度用量';

CREATE TABLE IF NOT EXISTS quota_orders (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_no      VARCHAR(32)  NOT NULL COMMENT '订单号',
  org_id        CHAR(16)     NOT NULL,
  package_type  VARCHAR(16)  NOT NULL COMMENT 'payg / pack30 / pack100',
  quota_amount  INT          NOT NULL COMMENT '增加配额数',
  price_cents   INT          NOT NULL COMMENT '价格 (分)',
  status        VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/cancelled',
  paid_at       DATETIME     NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_order_no (order_no),
  KEY idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='评估配额订单';
