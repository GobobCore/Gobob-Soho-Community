-- ============================================================================
-- Gobob SOHO — 全量数据库 schema
-- ============================================================================
-- 原则（吸取 Gobob 主仓教训）：所有 DDL 集中在这一个文件，分散的 migrations 是坑。
-- 所有业务表带 org_id 做机构隔离。字符集 utf8mb4。
--
-- 初始化：mysql gobob_soho < schema.sql && mysql gobob_soho < seed.sql
-- （docker-compose 已自动化，见 deploy/）
-- ============================================================================

SET NAMES utf8mb4;

-- ─────────────────────────────────────────────────────────────
-- 0. 机构（多租户根）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orgs (
    id          VARCHAR(64) PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(64) UNIQUE DEFAULT NULL,
    address     VARCHAR(500) DEFAULT NULL,
    phone       VARCHAR(50) DEFAULT NULL,
    email       VARCHAR(200) DEFAULT NULL,
    website     VARCHAR(500) DEFAULT NULL,
    logo_url    VARCHAR(500) DEFAULT NULL,
    description TEXT DEFAULT NULL,
    contact_name VARCHAR(100) DEFAULT NULL,
    -- Gobob Data API 授权（也可放 env，这里支持未来多机构各自配 Key）
    gobob_api_key VARCHAR(128) DEFAULT NULL,
    settings    JSON DEFAULT NULL,
    plan_status ENUM('free','trial','paid','suspended') NOT NULL DEFAULT 'free',
    seats_paid  INT NOT NULL DEFAULT 0,
    paid_until  DATE DEFAULT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 1. 账号与成员（双层模型：accounts 登录凭证 + members 业务身份）
--    角色：owner（老板/主管）/ advisor（顾问·老师）/ student / parent
--    is_virtual：机构代建的无账号学生/家长档案（顾问代管学生核心能力）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS accounts (
    id            VARCHAR(64) PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,
    username      VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone         VARCHAR(50) DEFAULT NULL,
    email         VARCHAR(100) DEFAULT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_username (org_id, username),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS members (
    id          VARCHAR(64) PRIMARY KEY,
    org_id      VARCHAR(64) NOT NULL,
    account_id  VARCHAR(64) DEFAULT NULL COMMENT '登录账号；虚拟成员为 NULL',
    name        VARCHAR(100) NOT NULL,
    role        ENUM('owner','advisor','student','parent') NOT NULL,
    is_virtual  TINYINT(1) DEFAULT 0 COMMENT '机构代建的无账号成员',
    phone       VARCHAR(50) DEFAULT NULL,
    email       VARCHAR(100) DEFAULT NULL,
    wechat      VARCHAR(100) DEFAULT NULL,
    -- 员工（advisor）扩展信息
    title       VARCHAR(100) DEFAULT NULL COMMENT '头衔，如 资深顾问',
    specialty   VARCHAR(255) DEFAULT NULL COMMENT '擅长方向',
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_role (org_id, role),
    INDEX idx_account (account_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 家长 ↔ 学生 关联
CREATE TABLE IF NOT EXISTS member_relationships (
    id              VARCHAR(64) PRIMARY KEY,
    org_id          VARCHAR(64) NOT NULL,
    from_member_id  VARCHAR(64) NOT NULL COMMENT '家长',
    to_member_id    VARCHAR(64) NOT NULL COMMENT '学生',
    rel_type        VARCHAR(50) DEFAULT 'parent_of',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org (org_id),
    INDEX idx_to (to_member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 2. CRM 线索（落地自 Gobob docs/crm-subsystem-design.md，补 org_id 强制）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    lead_id       VARCHAR(64) PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,

    -- 学生信息
    student_name  VARCHAR(100),
    student_email VARCHAR(100),
    student_phone VARCHAR(50),
    student_wechat VARCHAR(100),
    student_grade VARCHAR(20),

    -- 家长信息
    parent_name   VARCHAR(100),
    parent_phone  VARCHAR(50),
    parent_wechat VARCHAR(100),

    -- 学术背景
    current_school VARCHAR(200),
    gpa           DECIMAL(4,2),
    gpa_scale     VARCHAR(10),
    major         VARCHAR(100),

    -- 语言成绩
    language_test VARCHAR(50),
    current_score DECIMAL(6,2),
    target_score  DECIMAL(6,2),

    -- 留学意向
    target_countries JSON,
    target_degrees   JSON,
    target_majors    JSON,
    target_year      INT,
    budget_range     VARCHAR(50),

    -- 线索管理
    source        VARCHAR(50) COMMENT 'assessment(获客门户)/线上咨询/转介绍/讲座/广告/地推',
    source_detail VARCHAR(200),
    status        VARCHAR(50) DEFAULT 'new' COMMENT 'new/contacted/qualified/proposal/negotiation/converted/lost',
    priority      INT DEFAULT 3,

    -- 关联（转化后填充）
    member_id     VARCHAR(64),
    account_id    VARCHAR(64),
    assessment_id VARCHAR(64) COMMENT '关联评估快照（若来自获客门户）',

    -- 分配与归属
    assigned_advisor_id VARCHAR(64),
    assigned_mentor_id  VARCHAR(64),
    team_members        JSON,

    -- 时间线
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    contacted_at    DATETIME NULL,
    last_contact_at DATETIME NULL,
    next_contact_at DATETIME NULL,
    converted_at    DATETIME NULL,

    tags  JSON,
    notes TEXT,

    is_recycled     TINYINT(1) DEFAULT 0,
    recycled_at     DATETIME NULL,
    recycled_reason VARCHAR(200),

    INDEX idx_org_status (org_id, status),
    INDEX idx_assigned (assigned_advisor_id),
    INDEX idx_member (member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lead_activities (
    activity_id   VARCHAR(64) PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,
    lead_id       VARCHAR(64) NOT NULL,
    activity_type VARCHAR(50) COMMENT 'call/wechat/meeting/email/visit/note/status_change',
    subject       VARCHAR(200),
    content       TEXT,
    direction     VARCHAR(20) COMMENT 'inbound/outbound',
    contact_type  VARCHAR(20) COMMENT 'student/parent/both',
    contact_name  VARCHAR(100),
    outcome       VARCHAR(50),
    follow_up_required TINYINT(1) DEFAULT 0,
    follow_up_date DATETIME NULL,
    actor_member_id VARCHAR(64),
    actor_name    VARCHAR(100),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org_lead (org_id, lead_id),
    INDEX idx_lead (lead_id),
    INDEX idx_actor (actor_member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lead_conversions (
    conversion_id VARCHAR(64) PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,
    lead_id       VARCHAR(64) NOT NULL,
    from_status   VARCHAR(50),
    member_id     VARCHAR(64),
    account_id    VARCHAR(64),
    conversion_type VARCHAR(50) COMMENT 'signup/invitation/contract/manual',
    triggered_by  VARCHAR(64),
    triggered_at  DATETIME,
    contract_signed TINYINT(1) DEFAULT 0,
    contract_amount DECIMAL(12,2),
    contract_date DATE,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org (org_id),
    INDEX idx_lead (lead_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS lead_pipeline_stages (
    stage_id   VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    name       VARCHAR(100),
    sort_order INT,
    is_start   TINYINT(1) DEFAULT 0,
    is_won     TINYINT(1) DEFAULT 0,
    is_lost    TINYINT(1) DEFAULT 0,
    max_days   INT COMMENT '停留超时预警',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 3. 签约（合同 + 收款登记，线下收款无支付网关）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS service_modules (
    id          VARCHAR(64) PRIMARY KEY,
    code        VARCHAR(64) NOT NULL UNIQUE,
    name_zh     VARCHAR(128) NOT NULL,
    name_en     VARCHAR(128),
    category    VARCHAR(64),
    description TEXT,
    base_price_cents BIGINT COMMENT '指导价（分），仅供参考',
    sort_order  INT DEFAULT 0,
    is_active   TINYINT(1) DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contracts (
    id            VARCHAR(64) PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,
    contract_no   VARCHAR(32) NOT NULL UNIQUE COMMENT 'CT20260915A1B2C3',
    student_member_id VARCHAR(64) NOT NULL,
    lead_id       VARCHAR(64) COMMENT '来源线索',
    modules       JSON COMMENT '服务包：[module_code,...]',
    total_amount  DECIMAL(12,2) NOT NULL COMMENT '合同总额（元）',
    signed_date   DATE,
    service_start DATE,
    service_end   DATE,
    status        ENUM('active','completed','terminated') DEFAULT 'active',
    notes         TEXT,
    created_by    VARCHAR(64),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_student (org_id, student_member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS contract_payments (
    id          VARCHAR(64) PRIMARY KEY,
    org_id      VARCHAR(64) NOT NULL,
    contract_id VARCHAR(64) NOT NULL,
    amount      DECIMAL(12,2) NOT NULL COMMENT '本次收款（元）',
    pay_type    VARCHAR(50) COMMENT '定金/中期/尾款/其他',
    pay_method  VARCHAR(50) COMMENT '微信/支付宝/对公转账/现金',
    paid_at     DATE,
    note        VARCHAR(255),
    recorded_by VARCHAR(64),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org_contract (org_id, contract_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 4. 学生档案
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_profile (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL,
    real_name  VARCHAR(100),
    gender     VARCHAR(10),
    birth_date DATE,
    id_number  VARCHAR(50),
    address    VARCHAR(255),
    extra      JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_member (member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS academic_profile (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL,
    current_school VARCHAR(200),
    grade      VARCHAR(20),
    gpa        DECIMAL(4,2),
    gpa_scale  VARCHAR(10),
    language_scores JSON COMMENT '[{test,score,date}]',
    extra      JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_member (member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS study_intent (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL,
    target_countries JSON,
    target_degrees   JSON,
    target_majors    JSON,
    target_year INT,
    budget_min  DECIMAL(12,2),
    budget_max  DECIMAL(12,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_member (member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 5. 服务分配与换师（核心：按环节分配老师 + 交接）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS service_assignments (
    id            VARCHAR(64) PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,
    student_member_id VARCHAR(64) NOT NULL,
    advisor_member_id VARCHAR(64) NOT NULL COMMENT '负责老师',
    phase         VARCHAR(30) NOT NULL COMMENT 'overall/exam/writing/school/interview/visa/other',
    status        ENUM('pending','active','completed','transferred','cancelled') DEFAULT 'active',
    -- 换师交接
    transferred_to  VARCHAR(64) COMMENT '接替的 assignment id',
    handover_note   TEXT COMMENT '交接说明',
    started_at    DATETIME NULL,
    completed_at  DATETIME NULL,
    created_by    VARCHAR(64),
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_student (org_id, student_member_id),
    INDEX idx_org_advisor (org_id, advisor_member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS deliverables (
    id            VARCHAR(64) PRIMARY KEY,
    org_id        VARCHAR(64) NOT NULL,
    assignment_id VARCHAR(64),
    student_member_id VARCHAR(64) NOT NULL,
    advisor_member_id VARCHAR(64),
    title         VARCHAR(200),
    module_code   VARCHAR(64),
    status        ENUM('draft','in_review','revised','accepted') DEFAULT 'draft',
    file_url      VARCHAR(512),
    content       TEXT,
    submitted_at  DATETIME NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_student (org_id, student_member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 6. 进程管理（申请 / 里程碑 / 任务 / 文档 / 推荐信 / 通知）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS applications (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL COMMENT '学生',
    gobob_school_id VARCHAR(64) COMMENT '引用 Gobob 院校（不建外键）',
    school_name VARCHAR(200) COMMENT '冗余校名，远程不可用时仍可显示',
    program_name VARCHAR(200),
    degree     VARCHAR(30),
    status     VARCHAR(50) DEFAULT 'preparing' COMMENT 'preparing/submitted/under_review/interview/offer/rejection/waitlist',
    deadline   DATE,
    submitted_at DATETIME NULL,
    result_type VARCHAR(30),
    notes      TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_member (org_id, member_id),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS milestones (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL,
    title      VARCHAR(200) NOT NULL,
    category   VARCHAR(50) COMMENT 'exam/application/document/visa/financial/travel/other',
    phase      VARCHAR(30) COMMENT '对应 service_assignments.phase',
    due_date   DATE,
    status     VARCHAR(30) DEFAULT 'pending' COMMENT 'pending/in_progress/done/cancelled',
    sort_order INT DEFAULT 0,
    completed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_member (org_id, member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tasks (
    id          VARCHAR(64) PRIMARY KEY,
    org_id      VARCHAR(64) NOT NULL,
    member_id   VARCHAR(64) NOT NULL COMMENT '学生',
    milestone_id VARCHAR(64),
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    phase       VARCHAR(30),
    assignee_type VARCHAR(30) DEFAULT 'student' COMMENT 'student/advisor',
    assignee_member_id VARCHAR(64) COMMENT '若 assignee_type=advisor 则为负责老师',
    due_date    DATE,
    status      VARCHAR(30) DEFAULT 'pending' COMMENT 'pending/in_progress/done/cancelled',
    deliverable_type VARCHAR(50),
    sort_order  INT DEFAULT 0,
    completed_at DATETIME NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_member (org_id, member_id),
    INDEX idx_org_assignee (org_id, assignee_member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL,
    name       VARCHAR(255),
    category   VARCHAR(50) COMMENT 'transcript/passport/essay/offer/visa/other',
    file_path  VARCHAR(512),
    file_size  BIGINT,
    mime_type  VARCHAR(100),
    uploaded_by VARCHAR(64),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org_member (org_id, member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS recommendations (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL,
    recommender_name VARCHAR(100),
    recommender_title VARCHAR(100),
    status     VARCHAR(30) DEFAULT 'pending' COMMENT 'pending/requested/submitted/received',
    due_date   DATE,
    notes      TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_member (org_id, member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    member_id  VARCHAR(64) NOT NULL COMMENT '接收人',
    title      VARCHAR(255),
    content    TEXT,
    type       VARCHAR(50) COMMENT 'deadline/task/system/handover/contract',
    is_read    TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org_member_read (org_id, member_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 7. 任务模板（机构自定义服务流程，无市场 fork/star）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_templates (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    name       VARCHAR(200) NOT NULL,
    description TEXT,
    is_active  TINYINT(1) DEFAULT 1,
    created_by VARCHAR(64),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS task_template_items (
    id          VARCHAR(64) PRIMARY KEY,
    template_id VARCHAR(64) NOT NULL,
    title       VARCHAR(200) NOT NULL,
    phase       VARCHAR(30),
    assignee_type VARCHAR(30) DEFAULT 'student',
    offset_days INT COMMENT '相对服务开始日的天数',
    sort_order  INT DEFAULT 0,
    INDEX idx_template (template_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 8. 消息（学生/家长 ↔ 顾问，放宽 Gobob 原 student↔mentor 白名单）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id           VARCHAR(64) PRIMARY KEY,
    org_id       VARCHAR(64) NOT NULL,
    conversation_id VARCHAR(64) NOT NULL COMMENT '双方 member_id 排序哈希',
    sender_member_id   VARCHAR(64) NOT NULL,
    receiver_member_id VARCHAR(64) NOT NULL,
    content      TEXT,
    attachments  JSON,
    is_read      TINYINT(1) DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org_conv (org_id, conversation_id),
    INDEX idx_receiver (receiver_member_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 9. 评估快照（结果存本地；院校数据仍远程调 Gobob）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assessments (
    id           VARCHAR(64) PRIMARY KEY,
    org_id       VARCHAR(64),
    lead_id      VARCHAR(64) COMMENT '关联线索（若来自获客留资）',
    member_id    VARCHAR(64) COMMENT '关联学生（若已转化）',
    gobob_assessment_id VARCHAR(64) COMMENT 'Gobob 侧评估 id',
    form_json    JSON,
    result_json  JSON,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org (org_id),
    INDEX idx_lead (lead_id),
    INDEX idx_member (member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 10. Gobob 数据本地缓存
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gobob_api_cache (
    cache_key  VARCHAR(255) PRIMARY KEY,
    payload    JSON,
    expires_at DATETIME,
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─────────────────────────────────────────────────────────────
-- 11. 审计（换师 / 签约 / 转化等关键操作）
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id         VARCHAR(64) PRIMARY KEY,
    org_id     VARCHAR(64) NOT NULL,
    actor_member_id VARCHAR(64),
    action     VARCHAR(100) COMMENT 'handover/contract_sign/lead_convert/...',
    target_type VARCHAR(50),
    target_id  VARCHAR(64),
    detail     JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_org_action (org_id, action),
    INDEX idx_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
