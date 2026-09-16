# Gobob SOHO 拆分规划: SaaS 版 (闭源) vs 开源社区版 (公开)

> **日期**: 2026-09-16 · **起草**: cecilia · **状态**: 待 PM 评审
> **关联**: 本规划替代 `docs/GOBOb_SOHO_PLAN_2026-09-15.md` 的部署模型部分

---

## 0. 问题定义

Gobob SOHO 有两个产品, 商业模式完全不同, 代码却共享业务核心:

| | **SOHO 社区版** (开源) | **SOHO SaaS 版** (闭源) |
|---|---|---|
| 仓库 | GitHub `GobobCore/Gobob-SOHO` 公开 | intsch Gitea 私有 |
| License | Apache-2.0 | 内部 |
| 部署 | 机构自托管 (docker-compose 一键起) | 我们官方托管 (多机构 SaaS) |
| 收费 | 软件免费, 按次买 Gobob Data API Key (¥1/次) | 订阅: 1-2 协作账号免费, ≥3 每账号 ¥1000/年 |
| 机构数 | 单机构 (1 个 org) | 多机构 (N 个 org 共享一套) |
| 智能评估 | 公开, 留资进 leads (单机构) | 公开, 留资按机构 slug 分流 |
| 计费 | 无 | 有 (订阅 + 按次购买 + 运营后台) |
| 用户 | 机构自部署 | 机构是我们的客户 |

**核心矛盾**:
- 业务核心 (leads/contracts/students/assignments/workflow) 两版共享, 需要统一迭代
- 但 SaaS 版的计费/多机构/运营后台不能泄到开源版 (商业保护)
- 现有代码全混在 `backend/api/*.py`, 没有边界

---

## 1. 拆分方案: 单 repo + 目录拆分 (community / cloud / shared)

> 参考: GitLab CE/EE, Sentry, Metabase 都这么做

### 1.1 目标目录结构

```
gobob-soho/                        # 同一个 git repo
├── shared/                        # 共享业务核心 (两版都用)
│   ├── backend-core/              # FastAPI 业务路由 + core 模块
│   │   ├── core/                  # database/auth/id_gen/config/tenancy/gobob_client
│   │   ├── api/                   # leads/contracts/students/assignments/workflow/templates/messages/dashboard
│   │   ├── sql/                   # schema.sql + seed.sql
│   │   └── main.py                # FastAPI app 工厂 (create_app)
│   └── frontend-shared/           # 前端共用组件 (SchoolCard/Container/Card 等)
│       └── components/
│
├── community/                     # 开源版 — 推到 GitHub (Apache-2.0)
│   ├── backend/                   # FastAPI 入口 (import shared.backend-core)
│   │   └── main.py                # from shared.backend_core.main import create_app
│   ├── portal/                    # Next.js (单机构版)
│   ├── app/                       # Vue 3 SPA (单机构版)
│   ├── docker-compose.yml
│   ├── deploy/                    # systemd / docker / nginx
│   └── README.md + LICENSE
│
└── cloud/                         # SaaS 版 — 闭源, 只推 intsch
    ├── backend-saas/              # SaaS 扩展层 (import shared.backend-core)
    │   ├── api/saas_admin.py      # 运营后台 API (机构账户/账单/开源版订单/用量)
    │   ├── api/multi_tenant.py    # org_id 注入 + 多机构路由
    │   ├── api/billing.py         # 订阅计费 (免费 2 席, 超额 ¥1000/账号/年)
    │   └── main.py                # 入口: shared.main + SaaS 扩展 router
    ├── portal-saas/               # Next.js (多机构版, ?org=demo-studio)
    ├── app-saas/                  # Vue 3 SPA (多机构版)
    ├── soho-ops/                  # SaaS 运营后台 (19004, 已有)
    └── deploy-saas/               # 部署脚本 (多机构 SaaS 部署)
```

### 1.2 共享层 (shared/) 边界

**进 shared/**:
- 业务路由: leads/contracts/students/assignments/workflow/templates/messages/dashboard
- core 基础: database/auth/id_gen/config/tenancy/gobob_client
- 前端共用组件: SchoolCard/Container/Card/SchoolPicker/MajorPicker

**进 cloud/** (SaaS 版独有):
- `saas_admin.py` — SaaS 运营后台 API (orgs 订阅/账单/key-orders/usage)
- `billing.py` — 订阅计费 + 按次购买集成 (Gobob payment)
- `multi_tenant.py` — org_id 注入 + 多机构路由中间件
- `portal-saas/` — 多机构 portal (?org=slug 分流)
- `app-saas/` — 多机构 app
- `soho-ops/` — SaaS 运营后台 (已有)

**进 community/** (开源版独有):
- 单机构版 portal/app (不带 ?org= 参数)
- 单机构版 backend (org_id 从 env 读, 默认 default_org)
- 简化的 docker-compose (无 SaaS 计费, 无运营后台)

### 1.3 依赖关系

```
cloud/backend-saas/main.py
    ├─ import shared.backend_core.main  (业务核心)
    ├─ import cloud.api.saas_admin     (SaaS 扩展)
    └─ import cloud.api.billing        (计费)

community/backend/main.py
    └─ import shared.backend_core.main  (业务核心)
```

**shared/ 不知道 cloud/ 存在** — 单向依赖, cloud 可以扩展 shared 但 shared 不引用 cloud.

---

## 2. 拆分执行计划 (按周)

### Phase 1: 目录重组 (本周)

| 任务 | 产出 | 预估 |
|---|---|---|
| 1.1 建 shared/ + community/ + cloud/ 目录结构 | 目录骨架 | 0.5d |
| 1.2 把现有 backend/ + portal/ + app/ 拆到 community/ + shared/ | 业务核心移到 shared/, 单机构特有留 community/ | 1d |
| 1.3 把 saas_admin.py + soho-ops/ 移到 cloud/ | SaaS 闭源部分独立 | 0.5d |
| 1.4 现有功能回归测试 (E2E) | 所有现有功能不破 | 0.5d |
| 1.5 git subtree split 配置 | community/ 推到 GitHub, cloud/ 留在 intsch | 0.5d |
| **里程碑 M1** | **拆分完成, 两版各自独立可跑** | |

### Phase 2: SaaS 版完善 (下周)

| 任务 | 产出 | 预估 |
|---|---|---|
| 2.1 cloud/backend-saas/main.py 入口 (shared + SaaS 扩展) | SaaS backend 可跑 | 0.5d |
| 2.2 cloud/portal-saas 多机构支持 (?org=demo-studio) | SaaS portal 可跑 | 1d |
| 2.3 cloud/app-saas 多机构 app | SaaS app 可跑 | 1d |
| 2.4 计费逻辑 (billing.py): 免费 2 席, 超额 ¥1000/账号/年, 自动停用 | SaaS 计费闭环 | 1d |
| 2.5 机构自助注册 (SaaS 版, 已在 shared/) | SaaS 注册页 | 已有 |
| **里程碑 M2** | **SaaS 版完整可运营** | |

### Phase 3: 开源版打磨 (第 3 周)

| 任务 | 产出 | 预估 |
|---|---|---|
| 3.1 community/ 独立可跑 (无 cloud 依赖) | 开源版独立 | 0.5d |
| 3.2 开源版 README + LICENSE + CONTRIBUTING | 开源合规 | 0.5d |
| 3.3 git subtree split 推到 GitHub | 公开上线 | 0.5d |
| 3.4 开源版 docker-compose 一键起验证 | 新人 5 分钟跑起来 | 0.5d |
| **里程碑 M3** | **开源版 GitHub 公开** | |

---

## 3. 关键决策点

### 决策 1: shared/ 是 git submodule 还是 目录内共享?

**推荐: 目录内共享 (同一 repo, 同一 commit)**

理由:
- 业务核心改动需要同时影响两版, submodule 要跨 repo 提交麻烦
- git subtree split 可以把 shared/ 也推到 GitHub (开源版需要)
- 单 commit 修改 shared/, 两版同时生效

### 决策 2: community/ 推到 GitHub 的方式

**推荐: git subtree split**

```bash
# 把 community/ 子目录推到 GitHub (独立历史)
git subtree push --prefix=community https://github.com/GobobCore/Gobob-SOHO-Community.git main

# 或者: 用 GitHub Actions 自动 subtree split
```

**备选**: 双 repo (community 独立 repo, cloud 是另一个 repo 加 community 为 submodule) — 不推荐, 同步麻烦.

### 决策 3: SaaS 版部署端口

| 端口 | 服务 | 说明 |
|---|---|---|
| 19001 | shared backend (业务核心) | 两版共用 |
| 19002 | portal-saas (多机构) | SaaS 版获客门户 |
| 19003 | app-saas (多机构) | SaaS 版服务平台 |
| 19004 | soho-ops (已有) | SaaS 运营后台 |
| 19011 | portal-community (单机构) | 开源版获客门户 |
| 19012 | app-community (单机构) | 开源版服务平台 |
| 19013 | backend-community | 开源版 backend |

> 选 1901x 段避开 SaaS 版 1900x, 跟 CLAUDE.md 命名约定一致 (不冲突).

---

## 4. 智能评估页多机构识别 (问题 1)

**方案: URL 参数 `?org=demo-studio`**

### 4.1 机构注册时选 slug

```sql
ALTER TABLE orgs ADD COLUMN slug VARCHAR(64) UNIQUE NOT NULL COMMENT '机构 slug, 用于 portal ?org= 参数';
```

注册时让机构选 slug (唯一, 字母数字):
- 例: "demo-studio" → portal.gobob.cn/?org=demo-studio

### 4.2 智能评估页识别

```typescript
// portal-saas/app/assessment/page.tsx
const orgSlug = searchParams.get('org') || 'default';
// 调后端时带 org=slug
fetch(`/api/leads/capture?org=${orgSlug}`, ...)
```

后端 `/api/leads/capture` 改成:
```python
# 从 query param 拿 org slug, 查 org_id, 写 leads.org_id
org_slug = request.query_params.get('org', 'default')
org_id = lookup_org_by_slug(org_slug)
# INSERT leads (org_id=org_id, ...)
```

### 4.3 机构看到自己的留资

- SaaS app (app-saas) 登录后按 org_id 过滤
- 机构在 app 里能看到自己专属的「智能评估页链接」(例: `https://portal.gobob.cn/?org=demo-studio`), 复制发给客户

---

## 5. 风险 + 缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| 目录重组破坏现有功能 | 🟡 中 | Phase 1.4 全量 E2E 回归测试; 每次只移一个模块, 验证后再移下一个 |
| git subtree split 学习成本 | 🟢 低 | 先用一次, 写进 OPS.md |
| SaaS 版代码误推到 GitHub | 🔴 高 | .gitignore 加 cloud/; GitHub Actions 检查 push 时不含 cloud/ |
| 机构 slug 冲突 | 🟢 低 | UNIQUE 约束 + 注册时校验 |
| 开源版功能落后 SaaS 版 | 🟡 中 | 业务核心在 shared/, 两版同步; SaaS 只在 cloud/ 加扩展 |

---

## 6. 下一步 (待 PM 拍板)

1. **确认拆分方案** — 单 repo + 目录拆分 (community/cloud/shared)
2. **确认 Phase 1 范围** — 只做目录重组 + subtree split, 不动业务逻辑
3. **确认智能评估识别方式** — URL 参数 ?org=demo-studio
4. **确认端口分配** — SaaS 1900x, 开源版 1901x

确认后我按 Phase 1 开始动手.
