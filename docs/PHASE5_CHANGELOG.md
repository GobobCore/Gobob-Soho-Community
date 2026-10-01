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

---

# 2026-10-01 — 安全加固 + 测试基建 + CI 首次真正运行

> 起因: 盘点代码时发现公开仓闭源泄漏已持续两周未处理, 且 CI 长期为红。

## 安全

**公开仓闭源泄漏修复**（`Gobob-Soho-Community`，`private: false`）
- 事故成因: 2026-09-17 的 `--force` push 将含 `saas/` 的完整 monorepo 推入公开仓；
  `release_community.sh` 原本的设计是「先推后删」，等于每次发布主动开泄漏窗口，
  且补救从未成功执行。48 个 SaaS 闭源文件在公开仓挂了约两周。
- 处置: `git filter-repo` 重写历史 91→51 提交，删去 `saas/`、内部战略文档、
  `release.yml`、内部发布脚本与 `tmp_quota_view.js`。
- 全 91 提交扫描（高置信模式 + 熵值）确认**无真实凭据泄露**，故无需密钥轮换。
- 根因修复: 发布脚本改为**推送前**在临时副本剥离闭源路径，并设三道闸
  （逐提交扫描禁止路径 / 内部敏感词 / `community/`+`shared/` 完整性）。
- 社区文档去内部化：安装指令从私有仓改为公开仓，移除生产 API Key id。

## 测试基建

原 CI **不跑任何测试**，只做 import 检查、portal 构建、SQL 语法。本次:
- 新增 `backend-test` job，跑全量 pytest（含行为级依赖兼容验证）
- 修 `conftest.py` 路径 bug（`_BACKEND_CORE` 变量名与实际取值不符，测试存在隐式顺序依赖）
- 修 mock 字段名（`gpa` → `current_gpa`，与 gobob 真实 schema 对齐）
- 修 `ci.yml` 既有 YAML 语法错误（`name` 值含未加引号冒号）——**该配置自加入起
  GitHub Actions 就无法解析**，修好后 CI 首次真正运行，随即暴露后续两个问题
- 结果: 9 个 collection error → **70 passed / 3 skipped**

## 架构修复

- `shared/orgs_me.py` 原硬查 3 张 SaaS 专属表，社区部署中这些表不存在 → **必然 500**。
  改为表存在性探测，社区版返回 `billing_available=false` 并优雅降级。
- `saas_key_orders` 原仅存 `org_name`，机构改名后历史订单全部孤儿化。
  新增 `v0.23.0` migration 加 `org_id` 并回填（仅唯一匹配行）。
- 修 `v0.22.0` 语法错误：`year_month` 是 MySQL 保留字，当列名未加反引号，
  该 migration **从未跑通过**。

## 功能

- 评估链路对齐 gobob `phase3.MatchRequest` 真实 schema；新增评估历史/详情端点
- portal 多机构 `?org=<slug>` 持久化 + 机构自助注册页
- soho-app 新增 6 个视图（订单用量 / 用户 / 模板 / 智能选校 / 评估报告 / 个人资料）
- 订阅自助化：席位升级、自助取消订单
