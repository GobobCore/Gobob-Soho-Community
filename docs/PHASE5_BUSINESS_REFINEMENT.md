# Gobob SOHO 业务细化方案（Phase 5）

> 2026-09-15 · 待 review
> 目标：4 类痛点一次性全上（线索流转 / 合同明细 / 任务依赖 / 多家长）
> 角色不扩（owner/advisor/student/parent 4 角色保持）

---

## 一、线索流转管控

### 1.1 现状

`leads` 有 `student_phone` / `student_wechat` / `assigned_advisor_id` / `status` / `is_recycled`，但**无查重**、**无撞单检测**、**无超时回收**、**无流失原因分类**、**无来源 ROI 精细化**。结果：同一家长在不同时间被多个顾问分别录入 → 抢单纠纷；7 天不跟进的线索躺在顾问名下浪费。

### 1.2 改动

#### A. 录入时自动查重（双侧）
- 触发时机：`POST /api/leads` 和 `POST /api/leads/capture`
- 匹配规则：手机精确 OR 微信精确 OR (姓名相似度 ≥ 0.85 AND 家长手机后 7 位一致)
- 命中时接口返回 `200` + 字段 `duplicates: [{lead_id, student_name, assigned_advisor_name, status, created_at}]`，HTTP 仍 200
- 前端录入表单：命中时弹"疑似重复线索"卡片，列出已有线索，可选"仍要新建"或"打开已有"
- owner 视角"撞单工作台" `/api/leads/collisions`：列出近 30 天所有疑似重复组（按 lead_id 分组），可一键合并

#### B. 撞单合并
- `POST /api/leads/merge` body: `{keep_lead_id, merge_lead_ids: [...], reason}`
- 行为：保留 keep_lead_id 的所有字段；被合并线索的 `lead_activities` 全部迁移到 keep；`is_recycled=1, recycled_reason="merged to <keep_id>"`；写 audit_log
- 仅 owner 可操作

#### C. 线索公海 + 自动回收
- 配置项（机构级，写到 `orgs.settings` JSON 列）：`lead_recycle_days=7`（默认 7 天无跟进回公海）、`lead_aging_warn_days=3`（3 天未跟进开始告警）
- 后台 cron：每 30 分钟扫一次（复用现有 systemd timer 模式，1 行 shell）
  - `last_contact_at` 或 `created_at`（从未跟进）距今 > `lead_recycle_days` → `assigned_advisor_id=NULL, status='recycled'`，写 lead_activity "系统自动回收"
- 看板新增"公海"列：被回收的线索，无论原 status
- 顾问/owner 可"认领"：`POST /api/leads/{id}/claim` 写入 `assigned_advisor_id=self`

#### D. 流失原因分类（结构化）
- `lost_reason` 新枚举：`price_too_high`/`chose_competitor`/`decided_not_to_apply`/`lost_contact`/`other`
- 看板"已流失"列点击进入详情：必须选原因 + 写备注（≥10 字）才允许 `move-stage` 到 `lost`
- 报表 `GET /api/reports/loss-reasons`：流失原因分布饼图

#### E. 来源 ROI 精细化
- `leads.source` 从单值 VARCHAR 改成 `source_id` 引用 `lead_sources` 表（机构可自定义来源）
- 新表 `lead_sources(id, org_id, name, category, cost_cents)`，预置：线上咨询/转介绍/讲座/广告/地推/AI评估（与现有 seed 兼容）
- 报表 `GET /api/reports/source-roi`：

```json
[{"source":"AI评估","leads":12,"converted":3,"revenue_cents":120000,"cost_cents":0,"roi":"∞","cpa_cents":0}]
```

- 每个 source 可在设置里填获客成本（如讲座 5000 元/场），系统自动算 ROI / CPA

### 1.3 受影响文件

```
backend/sql/schema.sql        # +3 表（lead_sources 实际只是表名/列调整；lead_collisions 可省；流失原因枚举）；新建
backend/api/leads.py         # 录入查重、合并、认领、配置项
backend/api/reports.py       # 新建：流失原因、来源 ROI、撞单工作台
backend/scripts/             # 新建 lead_recycle_cron.py（30min 扫）
app/js/views.js              # 录入表单"疑似重复"卡片、流失弹窗、看板公海列、报表页
```

---

## 二、服务合同业务颗粒

### 2.1 现状

`contracts.modules` 存的是 JSON 数组 `["school_selection","essay_ps",...]`，只有总价，**没有每个模块的金额、状态、交付物关联**。结果：顾问不知道某学生 PS 模块完成了没；退费/转课只能手动调总额；学生买了选校+PS+申请，但 PS 撤了，财务要手算 8333.33 元。

### 2.2 改动

#### A. 合同项表 `contract_items`（核心新增）

```sql
CREATE TABLE contract_items (
  id          VARCHAR(64) PRIMARY KEY,
  org_id      VARCHAR(64) NOT NULL,
  contract_id VARCHAR(64) NOT NULL,           -- FK contracts.id
  module_code VARCHAR(64) NOT NULL,           -- service_modules.code
  amount      DECIMAL(12,2) NOT NULL,
  status      ENUM('pending','in_progress','delivered','completed','cancelled','refunded') DEFAULT 'pending',
  deliverable_id VARCHAR(64),                -- 关联 deliverables
  started_at  DATETIME,
  delivered_at DATETIME,
  completed_at DATETIME,
  refund_amount DECIMAL(12,2) DEFAULT 0,     -- 退费金额
  refunded_at   DATETIME,
  notes         TEXT,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_org_contract (org_id, contract_id),
  INDEX idx_status (status)
);
```

#### B. 合同创建接口升级
- `POST /api/contracts` body 新格式：

```json
{
  "student_member_id": "...",
  "lead_id": "...",
  "items": [
    {"module_code":"school_selection","amount":30000},
    {"module_code":"essay_ps","amount":50000},
    {"module_code":"application_fill","amount":30000}
  ],
  "signed_date":"2026-09-15",
  "service_start":"2026-09-15",
  "service_end":"2027-09-15",
  "notes":""
}
```

- total_amount 由后端从 items 求和计算（前端传也可，后端校验 =sum）
- 同步建 contract_items N 行（status='pending'）

#### C. 退费/转课
- 退某项：`POST /api/contracts/{cid}/items/{iid}/refund` body `{amount, reason}` → `status='refunded'`
- 已付款 = sum(contract_payments.amount)；退费 = sum(items.refund_amount)
- 合同剩余金额 = total - paid + refunded（前端显示）
- 全额退：`POST /api/contracts/{cid}/terminate` → `status='terminated'` + 所有 item status='cancelled'

#### D. 多合同并行
- 现状已支持（一个学生可多个 active 合同），前端"我的合同"页改为列表，每行点开看明细（合同项 + 进度 + 已收/待收）
- 后端 `GET /api/contracts?student_id=X` 排序：active 优先，再按 signed_date desc

#### E. 续约
- 合同 `service_end` 距今 ≤ 30 天：驾驶舱 + 学生端都显示"合同即将到期"
- 学生/家长点"续约"：`POST /api/contracts/{cid}/renew` body `{extend_months, new_items: [...]}`
  - 自动新建合同，contract_no 标后缀 "R1/R2"
  - 拷贝服务包项（金额可调）
  - 写 `lead_activity` 风格的"合同续约"记录

### 2.3 受影响文件

```
backend/sql/schema.sql        # contract_items 表新增（data 迁移：把现有 JSON 拆成行）
backend/api/contracts.py     # 全面升级（建/续/退/明细）
backend/api/assignments.py   # deliverable_id 关联 contract_items
app/js/views.js              # 合同页改成明细列表 + 续约按钮
app/index.html               # dashboard 增加"即将到期"卡片
```

---

## 三、服务交付过程（任务依赖 + 时间线）

### 3.1 现状

`tasks` 字段齐全但**无前置依赖**、**无可视化时间线**。结果：顾问勾掉"提交网申"但其实"选校清单"还没定，乱套；学生/家长看到一堆任务不分主次。

### 3.2 改动

#### A. 任务依赖（轻量级）
- 新表 `task_dependencies`：

```sql
CREATE TABLE task_dependencies (
  id          VARCHAR(64) PRIMARY KEY,
  org_id      VARCHAR(64) NOT NULL,
  task_id     VARCHAR(64) NOT NULL,
  depends_on  VARCHAR(64) NOT NULL,
  type        ENUM('hard','soft') DEFAULT 'hard',  -- hard=必须完成才能勾；soft=仅提示
  INDEX idx_task (task_id),
  INDEX idx_dep (depends_on)
);
```

- 模板编辑：可在创建/编辑任务时选"依赖某个其他任务"
- 状态切换时校验：`POST /api/workflow/tasks/{id}/status` body `{status:'done'}` 时：
  - hard 依赖未完成 → 422，列出未完成依赖
  - soft 依赖未完成 → 200，但响应里 `warnings: ["依赖: 选校清单（未完成）"]`
- 任务模板新建时也能带依赖（结构上需扩 templates item 表，加 `depends_on_item_key` 字段字符串引用同模板其他 item.title）

#### B. 时间线（Gantt 简化版）
- `GET /api/workflow/timeline?student_id=X` 返回：

```json
{
  "phases": [
    {"phase":"school","name":"选校","start":"2026-09-15","end":"2026-10-15","progress":0.5},
    ...
  ],
  "critical_path": ["确定选校清单","PS 初稿","提交网申","面试准备"],
  "next_blocker": "PS 初稿（前序：选校清单确定）"
}
```

- 阶段起止 = 该阶段任务里 min(due_date) / max(due_date)
- 进度 = done 任务数 / 总任务数
- 关键路径 = topo 排序后所有 hard 依赖串成的链
- 下个卡点 = critical_path 上第一个未完成且被硬依赖的
- 前端时间线：CSS grid 画横向 bar，hover 显示任务详情（**不上 Gantt 库**，纯 SVG 简单画，保持 CDN 静态站特性）

#### C. 交付物版本/审阅
- 现状：`deliverables` 只有单条记录，状态 in_review/accepted
- 改为：每次"出稿"是 `deliverable_versions` 一行：

```sql
CREATE TABLE deliverable_versions (
  id VARCHAR(64) PRIMARY KEY,
  deliverable_id VARCHAR(64) NOT NULL,
  version INT NOT NULL,
  content TEXT,
  file_url VARCHAR(512),
  submitted_at DATETIME,
  INDEX idx_deliv (deliverable_id)
);
```

- `deliverables.current_version` 指向最新；`status` 流转：`draft`（v1 创建）→ `submitted`（v1 提交）→ `reviewed`（主管/学生批）→ `accepted`（通过）or `rejected`（驳回→ 创建 v2）
- 审阅意见存 `deliverable_comments(version_id, reviewer_member_id, content, created_at)`
- 状态机校验：rejected 必须有评论；accepted 才能关联 contract_items.status='completed'

### 3.3 受影响文件

```
backend/sql/schema.sql        # +2 表（task_dependencies, deliverable_versions/comments）
backend/api/assignments.py   # deliverables 升级为多版本
backend/api/workflow.py      # 任务状态校验依赖、timeline 端点
app/js/views.js              # 学生详情 tab 增加时间线；交付物出 v1/v2 弹窗
```

---

## 四、多家长 / 多学生关系

### 4.1 现状

`member_relationships` 表是单向 `from→to`（家长→学生），只有 create 没用起来。SOHO 现实：同家长 2 个孩子（兄弟/姐妹）；家长代签合同（学生未成年）；家长代付款（学生已成人但钱家长出）。

### 4.2 改动

#### A. 关系多对多
- 现状 `member_relationships` 已支持多对多（行级存多行），无需改表
- 补 API：
  - `GET /api/members/{id}/students`（一个家长关联的所有学生）
  - `GET /api/students/{id}/parents`（一个学生的所有家长，含关系类型：父亲/母亲/其他监护人）
  - `POST /api/members/relationships` body `{from_member_id, to_member_id, rel_type:'father'|'mother'|'guardian'|'self', is_financial_payer:bool}`

#### B. 家长代签
- `contracts.signed_by_type ENUM('student','parent')` + `signed_by_member_id`
- 合同详情显示"代签人：张同学母亲 李女士"
- 合同创建时可指定 `signed_by_member_id`（必须是学生的关联家长）

#### C. 家长独立账号（已有，扩权限）
- 现状 parent 登录后默认只看关联学生（已实现）
- 新增：parent 可切换学生（顶部下拉框，若有 ≥2 个孩子）
- parent 可代付：合同详情"我要付款"按钮 → 复用现有 `add_payment` 端点
- parent 看进度：只看自己孩子（已实现）

#### D. 关系类型枚举
- `member_relationships.rel_type` 从 `VARCHAR(50)` 改为 `ENUM('father','mother','guardian','spouse','self')`
- 数据迁移：用 LIKE 匹配已有 'parent_of' 旧值 → 'guardian'，再人工查 father/mother（实际场景：录入时让选择）

### 4.3 受影响文件

```
backend/sql/schema.sql        # contracts 加 2 列、member_relationships 改枚举
backend/api/members.py       # 关系 API
backend/api/contracts.py     # 代签字段
backend/api/students.py      # 家长关联学生列表
app/js/views.js              # 家长顶部学生切换；合同代签信息展示
app/index.html               # 合同详情页加"代签人"
```

---

## 五、数据迁移（重要）

由于 Phase 5 加列/改枚举，**现有数据不能丢**。策略：

1. **加列**（add nullable + default 0）：无破坏
2. **改枚举**（`member_relationships.rel_type`、`contracts.signed_by_type`）：先 `ALTER TABLE ... MODIFY ... VARCHAR(64)` 兼容旧值，再写脚本批量归一
3. **拆 JSON**（`contracts.modules` → `contract_items`）：启动时检测 `modules` 是 JSON 而 `contract_items` 表空 → 写一次性的数据迁移脚本
4. **数据迁移脚本** `backend/migrations/v0.16.0_phase5_refinement.sql` 幂等可重跑

---

## 六、实施步骤（一次拆完，2 周）

### 阶段 5.1：Schema 迁移 + 后端基础（4 天）
- D1-D2: `v0.16.0_phase5_refinement.sql` + 迁移脚本（拆合同 JSON、归一关系类型）
- D3-D4: 后端所有 API 升级（线索查重/合并/认领/公海、合同 items、任务依赖、版本交付物、家长关系）

### 阶段 5.2：后台 cron + 报表（2 天）
- D5: `lead_recycle_cron.py` + systemd timer
- D6: reports 端点（流失原因、来源 ROI、撞单工作台）

### 阶段 5.3：前端 UI（5 天）
- D7-D8: 线索录入查重提示 + 看板公海列 + 撞单工作台
- D9: 合同明细列表 + 续约弹窗 + 退费
- D10: 任务依赖提示 + 时间线 SVG
- D11: 交付物多版本 + 家长学生切换

### 阶段 5.4：测试 + 文档（3 天）
- D12-D13: E2E 测试（同 Phase 4 标准）
- D14: 文档更新

---

## 七、风险与备选

| 风险 | 缓解 |
|---|---|
| 合同 JSON 拆 items 时金额丢失（`base_price_cents` 是 module 表的，不是合同的） | 拆时用 `contracts.total_amount` 按比例分；用户后续可调 |
| 任务依赖环（A→B→A） | 写入时 DFS 检测，环则 422 |
| 30min cron 误回收（顾问临时有事） | 回收前 1 天提醒（写入通知），可"延期"或"认领续期" |
| 家长关系历史数据无 `rel_type`（老数据是 'parent_of'） | 启动迁移脚本归为 'guardian'，UI 上让 owner 二次确认 |
| 改 schema 后老 SOHO 部署无法升 | 写清晰的 migration 步骤到 docs/UPGRADE.md |

---

## 八、PM 拍板清单

请确认或调整：

1. **公海自动回收天数**（默认 7 天，可改）
2. **续约自动续期**（默认手动按钮触发，可改成"自动续"+提醒）
3. **任务依赖强度**（hard 必须先 / soft 仅警告）
4. **线索撞单合并策略**：a) 合并后老线索 404（推荐）b) 保留只读
5. **时间线渲染**：a) 纯 SVG 自绘（保持 CDN 静态）b) 引 dayjs 库做更花哨

确认后我开始 Phase 5.1（schema 迁移 + 后端）。
