# Phase 5 业务细化 — 变更文档

> 2026-09-15 · 已上线到 main

## 4 大痛点全部完成

### 1. 线索流转管控

**录入查重**（`/api/leads` POST）：录入时按手机精确 / 微信精确 / (姓名相似度≥0.85 + 家长手机后 7 位一致） 匹配，命中返回 `duplicates: [{lead_id, student_name, assigned_advisor_name, status, _match_reason}]`，HTTP 200。前端"疑似重复"卡片列出可选"打开已有"或"仍要新建"。

**撞单工作台**（`/api/leads/collisions` GET，owner）：按手机号/微信分组列近 30 天疑似重复组。

**合并**（`/api/leads/merge` POST，owner）：`{keep_lead_id, merge_lead_ids, reason}` → 被合并线索的 `lead_activities` 全部迁移到 keep，被合并标 `is_recycled=1, status='lost'`，写 audit_log。

**公海自动回收**（`backend/scripts/lead_recycle_cron.py`，30min systemd timer）：超 `lead_recycle_days` 天（默认 7，机构 `orgs.settings` 可配）未跟进 → `assigned_advisor_id=NULL, is_recycled=1, status='recycled'`；到期前 `lead_aging_warn_days` 天（默认 3）强提醒。**回滚**：`POST /api/leads/{id}/restore`（7 天内）。

**认领**（`/api/leads/{id}/claim` POST）：advisor 认领自己 / owner 需 body 传 `advisor_id`。

**流失原因必填**（`/api/leads/{id}/move-stage` status='lost'）：需 `lost_reason` 枚举（price_too_high/chose_competitor/decided_not_to_apply/lost_contact/other）+ `lost_detail` ≥10 字。

**来源 ROI 报表**（`/api/reports/source-roi` GET，owner）：每来源的 leads/converted/conv_rate/revenue/cost/cpa/roi。

**流失分析**（`/api/reports/loss-reasons` GET）：原因分布 + 占比。

### 2. 服务合同业务颗粒

**合同明细表 `contract_items`**：每模块独立金额/状态/交付物关联，不再 JSON blob。
- 建合同 `POST /api/contracts` body 用 `items: [{module_code, amount}, ...]`，total_amount 后端求和
- 合同详情含 `items[]` 数组（每项 status/amount/deliverable_id/refund_amount）
- 合同项状态流转：`POST /api/contracts/{cid}/items/{iid}/status`
- **退费**（owner）：`POST /api/contracts/{cid}/items/{iid}/refund` body `{amount, reason}`，校验 ≤ 已收款
- **续约**：`POST /api/contracts/{cid}/renew` body `{extend_months, new_items}` → 新建合同（号 `_R1/_R2`），拷贝服务项，自动衔接 service_start = 原 service_end（若未来到期）
- **家长代签**：`contracts.signed_by_type/signed_by_member_id` 列，创建时可指定关联家长

**多合同并行**：一个学生可多个 active 合同，列表按 active 优先 + signed_date desc 排。

### 3. 任务依赖 + 时间线

**任务依赖 `task_dependencies`**：task_id → depends_on + type(hard/soft)。
- 写时 DFS 环检测（A→B→A 422）
- 勾 `done` 时：hard 依赖未完成 → 422 列清单；soft 依赖未完成 → 200 + warnings[]
- CRUD：`POST /api/workflow/tasks/{tid}/dependencies` `GET .../dependencies`

**时间线 `GET /api/workflow/timeline?student_id=X`**：
- 各 phase 起止（min/max due_date）+ 进度（done/总）
- `critical_path`：所有 hard 依赖链
- `next_blocker`：未完成且被硬依赖的第一个任务（含 blocked_by）

**任务模板**：`task_template_items.depends_on_item_key`（模板内引用，实例化时自动展开）

### 4. 多家长/多学生

**关系多对多**：`member_relationships` 表已支持，补 API：
- `POST /api/relationships` 建关联（rel_type: father/mother/guardian/spouse/self）
- `GET /api/relationships/student/{id}/parents` 一个学生关联的所有家长
- `GET /api/relationships/parent/{id}/students` 一个家长关联的所有学生（家长切换用）
- `DELETE /api/relationships/{id}` 解除（owner）

**家长端**：登录后顶部下拉切换多个学生；合同/进度/任务按当前学生隔离。

### 交付物多版本（Phase 5 附带）

`deliverables` 升级为多版本：
- `POST /api/assignments/deliverables` 建 v1（draft）
- `POST /api/assignments/deliverables/{did}/versions` 出 v2/v3...
- `POST /api/assignments/deliverables/versions/{vid}/review` 审阅（approve/reject/comment + 必填意见）
- approve → `deliverables.status='accepted'` + 关联 contract_items.status='completed'
- reject → 回 draft，强制留 comment
- `GET /api/assignments/deliverables/{did}` 返回全版本+意见

## Schema 迁移

- `backend/migrations/v0.16.0_phase5_refinement.sql`：5 新表 + 5 列
- `backend/scripts/phase5_migrate_data.py`：幂等可重跑（拆合同 JSON、归一关系类型、绑定预置来源到机构）

## 新端点（88 → 93 个 API）

+ collisions / merge / claim / loss-reasons / source-roi / renew / items/{id}/status / items/{id}/refund / tasks/{id}/dependencies / timeline / deliverables/{did}/versions / deliverables/versions/{vid}/review / deliverables/{did} (全版本) / relationships CRUD
