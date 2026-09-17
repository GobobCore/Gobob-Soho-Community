# Gobob SOHO 三仓拆分说明 (R-Refactor 2026-09-17, 更新 2026-09-17 SaaS/社区物理隔离)

> **本仓 (Gobob-SOHO)** 是开发 monorepo, 含 `shared/` + `community/` + `saas/` 三层。
> Release 时用 `scripts/release_*.sh` 推到两个独立 GitHub repo (Community 公开 + SaaS 私有)。

---

## 三仓分工 (2026-09-17 物理隔离后)

| 仓 | 内容 | License | GitHub URL | 端口 |
|---|---|---|---|---|
| **`Gobob-SOHO`** (本仓, monorepo) | shared/ + community/ + saas/ 三层 | (内部, 不发布) | intsch Gitea | — |
| **`Gobob-Soho-Community`** | community/ + shared/ (扁平) | Apache-2.0 | github.com/GobobCore/Gobob-Soho-Community | 19011/19012/19013 |
| **`Gobob-Soho-SaaS`** | saas/ + shared/ (扁平) | proprietary (private) | github.com/GobobCore/Gobob-Soho-SaaS | 19001/19002/19003/19004 |

### 🔴 SaaS 与社区版代码边界(物理隔离,2026-09-17 落地)

| 维度 | SaaS 版 (saas/) | 社区版 (community/) |
|------|----------------|---------------------|
| **后端入口** | `saas/backend/main.py` (自带 saas_admin + billing router) | `community/backend/main.py` (只用 shared 核心) |
| **平台前端** | `saas/app/index.html` (brand: "SaaS 多机构版") | `community/app/index.html` (brand: "社区开源自托管版") |
| **运营后台** | `saas/soho-ops/index.html` | — (社区版无运营后台,本机 owner 角色自管) |
| **获客 portal** | 暂共用 `community/portal` (19002,Next.js) | `community/portal` (19012,Next.js) |
| **DB** | `gobob_soho` (多机构 + 计费表) | `gobob_soho_community` (单机构) |
| **systemd** | `gobob-soho-{backend,app,ops}.service` → `saas/` | `gobob-soho-community-{backend,app,portal}.service` → `community/` |
| **共用** | `shared/backend-core/` (业务核心, 两版都必须相同) | 同左 |

**绝不共用**:
- `saas/app/` ≠ `community/app/`(独立两份,品牌/文案不同)
- `saas/backend/api/{saas_admin,billing}.py` ≠ 任何 community 文件
- systemd unit 配置文件 (`~/.config/systemd/user/gobob-soho*.service`) 一一对应 saas 或 community,**不允许混用**

---

## 拆分流程 (release 时)

**简化版**: 用 `scripts/release_community.sh` 和 `scripts/release_saas.sh` 一键搞定,不再手动 subtree split。

### 1. 推社区版 (community/ + shared/)

```bash
cd /home/ricky/.openclaw/workspace/gobob-soho
./scripts/release_community.sh                # 推到 community-publish/main
./scripts/release_community.sh --dry-run      # 验证流程但不真推
```

### 2. 推 SaaS 版 (saas/ + shared/)

```bash
cd /home/ricky/.openclaw/workspace/gobob-soho
./scripts/release_saas.sh                     # 推到 saas-publish/main
./scripts/release_saas.sh --dry-run           # 验证流程但不真推
```

### 3. 后续开发同步

```bash
# 本仓改完, 推到三个远端
git push origin main                            # 主仓 (GitHub Gobob-SOHO, 内部 monorepo)
./scripts/release_community.sh                 # Community (Apache-2.0 公开)
./scripts/release_saas.sh                      # SaaS (proprietary 私有)
```

> ⚠️ **不要直接 `git subtree push`** — 用脚本,脚本里有敏感信息扫描和路径校验。
> ⚠️ **本仓改动后必须先 commit** — release 脚本会检查工作树干净。

---

## 历史路径警告

> ⚠️ 拆分前 (2026-09-16 之前) 的 commit 含 SaaS 商业代码:
> - `backend/api/saas_admin.py` (SaaS 运营后台)
> - `backend/api/billing.py` (计费)
> - `backend/scripts/aggregate_saas_usage.py` (用量聚合)
> - `backend/migrations/v0.17.0_saas_ops.sql` (SaaS migration)
>
> 这些 commit (`fc60997` `54cf502` `2a1b17d` 等) 仍在 git history 里。
> **只 push 拆分后的 commit** (不含 `cloud/` 的路径) 到 Community/SaaS 仓, 避免 SaaS 商业资产泄漏到 GitHub。

---

## shared/ 同步策略

`shared/` 是两版共用核心, 改一处两版都得更新。

| 方式 | 优点 | 缺点 |
|---|---|---|
| **手动 cp** (当前) | 简单直接 | 容易忘 |
| **Git subtree pull** | 自动同步 | 跨仓配置麻烦 |
| **Symbolic link / submodule** | 自动 | 增加复杂度 |

**当前**: 拆分时手动 `cp -r shared .` 进独立 repo。后续 GitHub Actions 加自动同步。

---

## 与之前决策的关系

- **`docs/REPO_STRATEGY_2026-09-16.md`** (历史): "不开独立 repo, 改用主仓" — **已被本文件覆盖**
- **`docs/SPLIT_PLAN_SAAS_VS_COMMUNITY_2026-09-16.md`**: 拆分方案, 决策点 4 个已拍:
  - SaaS 私有 ✅
  - shared/ 复制进每个 repo ✅
  - 主仓留 monorepo ✅
  - 现在就拆 ✅

---

**Last updated**: 2026-09-17 16:00 (cecilia + Claude, SaaS/社区版物理隔离 + cloud→saas 改名 + release 脚本化)

**关键变更 (vs 上一版)**:
- `cloud/` → `saas/`(避免"cloud=闭源"的隐喻混淆)
- `community/app/` 与 `saas/app/` 物理隔离,brand 文案各自维护
- systemd unit (`gobob-soho-{backend,app,ops}.service`) 全部指向 `saas/` 路径,不再用 community 代码兜底
- 发布脚本化:`scripts/release_community.sh` `scripts/release_saas.sh` 替代手动 subtree
- 后续 PM / cecilia 改 SaaS 走 saas/,改社区走 community/,**绝不允许跨边界混改**