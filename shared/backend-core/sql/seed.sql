-- ============================================================================
-- Gobob SOHO — 种子数据
-- 13 个服务模块 + 默认线索 pipeline 阶段（org 级默认在首次启动时也可补）
-- ============================================================================

SET NAMES utf8mb4;

-- ── 服务模块（13 个固定枚举，源自 Gobob 服务市场，机构可改指导价）──
INSERT INTO service_modules (id, code, name_zh, name_en, category, description, base_price_cents, sort_order, is_active) VALUES
('mod_school_selection', 'school_selection', '选校定位', 'School Selection', '规划', '根据学生背景和目标，提供选校清单和申请策略', 300000, 1, 1),
('mod_essay_ps', 'essay_ps', '文书-PS', 'Personal Statement', '文书', '个人陈述撰写、修改、润色', 500000, 2, 1),
('mod_essay_cv', 'essay_cv', '文书-CV', 'Curriculum Vitae', '文书', '简历优化、格式调整、内容提炼', 200000, 3, 1),
('mod_essay_recommendation', 'essay_recommendation', '推荐信', 'Recommendation Letter', '文书', '推荐信策略、撰写指导、推荐人沟通', 150000, 4, 1),
('mod_exam_toefl', 'exam_toefl', 'TOEFL 备考', 'TOEFL Preparation', '考试', '托福备考规划、提分策略、模考分析', 200000, 5, 1),
('mod_exam_ielts', 'exam_ielts', 'IELTS 备考', 'IELTS Preparation', '考试', '雅思备考规划、提分策略、模考分析', 200000, 6, 1),
('mod_exam_gre', 'exam_gre', 'GRE 备考', 'GRE Preparation', '考试', 'GRE 备考规划、提分策略、模考分析', 200000, 7, 1),
('mod_exam_gmat', 'exam_gmat', 'GMAT 备考', 'GMAT Preparation', '考试', 'GMAT 备考规划、提分策略、模考分析', 200000, 8, 1),
('mod_background_research', 'background_research', '背景提升', 'Background Enhancement', '背景', '实习/科研/活动规划，提升申请竞争力', 400000, 9, 1),
('mod_application_fill', 'application_fill', '网申递交', 'Application Submission', '申请', '网申系统填写、材料整理、提交跟进', 300000, 10, 1),
('mod_interview_prep', 'interview_prep', '面试辅导', 'Interview Preparation', '面试', '模拟面试、面试复盘、问题预测', 300000, 11, 1),
('mod_visa_ds160', 'visa_ds160', '签证辅导', 'Visa Guidance', '签证', 'DS-160 填写、面签模拟、材料准备', 250000, 12, 1),
('mod_pre_departure', 'pre_departure', '行前指导', 'Pre-departure Guide', '行前', 'Offer 选择、住宿机票、入学准备', 200000, 13, 1)
ON DUPLICATE KEY UPDATE
    name_zh = VALUES(name_zh),
    name_en = VALUES(name_en),
    category = VALUES(category),
    description = VALUES(description),
    base_price_cents = VALUES(base_price_cents),
    sort_order = VALUES(sort_order),
    is_active = VALUES(is_active),
    updated_at = NOW();

-- ── 默认线索 pipeline 阶段（机构可在设置里自定义；此处给一份通用默认）──
-- 注意：org_id 需在实例化机构时写入。docker 初始化用占位 'default'，
-- backend 首次启动 _bootstrap 会把 default 阶段的 org_id 更新为真实机构 id。
INSERT INTO lead_pipeline_stages (stage_id, org_id, name, sort_order, is_start, is_won, is_lost, max_days) VALUES
('st_new',        'default', '新线索',   1, 1, 0, 0, 3),
('st_contacted',  'default', '已联系',   2, 0, 0, 0, 7),
('st_qualified',  'default', '意向确认', 3, 0, 0, 0, 14),
('st_proposal',   'default', '方案报价', 4, 0, 0, 0, 14),
('st_negotiation','default', '签约谈判', 5, 0, 0, 0, 14),
('st_converted',  'default', '已签约',   6, 0, 1, 0, NULL),
('st_lost',       'default', '已流失',   7, 0, 0, 1, NULL)
ON DUPLICATE KEY UPDATE name = VALUES(name);
