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
| **获客 portal** | `saas/portal/` (19002, Next.js) | `community/portal/` (19012, Next.js) |
| **DB** | `gobob_soho` (多机构 + 计费表) | `gobob_soho_community` (单机构) |
| **systemd** | `gobob-soho-{backend,app,ops,portal}.service` → `saas/` | `gobob-soho-community-{backend,app,portal}.service` → `community/` |
| **共用** | `shared/backend-core/` (业务核心, 两版都必须相同) | 同左 |

### Portal 数据流(SaaS vs 社区版)

| 维度 | SaaS portal (19002) | 社区版 portal (19012) |
|------|---------------------|----------------------|
| Next.js 工作目录 | `saas/portal/` | `community/portal/` |
| 反代目标 BACKEND | `http://127.0.0.1:19001` (SaaS backend) | `http://127.0.0.1:19011` (社区版 backend) |
| 反代路径 | `/api/assessment/*`, `/api/leads/*`, `/api/register`, `/api/saas/*` | `/api/assessment/*`, `/api/leads/*` |
| 数据流向 | 留资 → SaaS backend `gobob_soho` (走多机构路由 `?org=slug`) | 留资 → 社区 backend `gobob_soho_community` (单一机构, 跟社区 app 同 backend 同库) |
| 自助注册 | ✅ SaaS 多机构 (`/api/register`) | ❌ 社区单机构 (无注册,机构手动建账号) |
| 收银台 | ✅ `/api/saas/*` (开源版按次购买,SaaS 收银台代理 Gobob payment) | ❌ 社区自托管无 SaaS 收银台 |

**绝不共用**:
- `saas/portal/` ≠ `community/portal/` (独立两份代码,各自配 BACKEND)
- `saas/app/` ≠ `community/app/`(独立两份,品牌/文案不同)
- `saas/backend/api/{saas_admin,billing}.py` ≠ 任何 community 文件
- systemd unit 配置文件 (`~/.config/systemd/user/gobob-soho*.service`) 一一对应 saas 或 community,**不允许混用**

**绝不共用**:
- `saas/app/` ≠ `community/app/`(独立两份,品牌/文案不同)
- `saas/backend/api/{saas_admin,billing}.py` ≠ 任何 community 文件
- systemd unit 配置文件 (`~/.config/systemd/user/gobob-soho*.service`) 一一对应 saas 或 community,**不允许混用**

---

## 拆分流程 (release 时)

**当前方案**: 用 `scripts/release_community.sh` 和 `scripts/release_saas.sh` 一键搞定,内部用 **mirror push + post-push hotfix 撤回** 策略。

### ⚠️ 历史教训(必读)

```
❌ 2026-09-17 16:30 P0 事故: 'git push origin main:community-publish/main --force'
   把 monorepo 整体历史(包括 saas/ 49 文件)推到 GitHub 社区公开仓.
   泄露时长 ~10 分钟, GitHub stars/forks/watchers 全部为 0, 实际访问者 ~0.
   13,486 行 SaaS 闭源代码曾在 commit 9e42294 中公开过, hotfix 64e683e 删除.

❌ 之前用 git subtree split --prefix=X 抽取单一路径, 但 git subtree 不支持多 --prefix,
   且 subtree 算法对 force-push 重写历史的场景不可靠 (返回与远端相同的 SHA, push 被忽略).

✅ 当前方案: mirror push + post-push hotfix 撤回 (release_*.sh 已固化).
```

### 实际推送流程 (release_community.sh 内部)

```bash
# Step 1: 工作树干净 + 敏感信息扫描 (脚本自动)
# Step 2: mirror push — 把 origin/main 整体历史推到远端
git push $COMMUNITY_REPO main:main --force

# Step 3: post-push hotfix — 在远端仓拉最新, 删 saas/, 再 push
git fetch $COMMUNITY_REPO main
git checkout -b hotfix-rm-saas FETCH_HEAD
git rm -rf saas/                     # 49 文件撤回
git commit -m "R-Security: hotfix 删除 saas/"
git push $COMMUNITY_REPO hotfix-rm-saas:main --force

# Step 4: 验证 — 用 grep -cE "\\bsaas/" 检测远端是否还有 saas/ 路径
git ls-tree -r $COMMUNITY_REPO/main | grep -cE "\bsaas/"
# 期望输出 0
```

### 1. 推社区版 (community/ + shared/)

```bash
cd /home/ricky/.openclaw/workspace/gobob-soho
./scripts/release_community.sh                # 推到 community-publish/main
./scripts/release_community.sh --dry-run      # 验证流程但不真推
```

**脚本效果**:
- Step 2 mirror push: community-publish 仓会临时出现 saas/ 49 文件(因为 monorepo 内有)
- Step 3 hotfix: 立即撤回 saas/
- Step 4 验证: `0` 表示干净

### 2. 推 SaaS 版 (saas/ + shared/)

```bash
cd /home/ricky/.openclaw/workspace/gobob-soho
./scripts/release_saas.sh                     # 推到 saas-publish/main
./scripts/release_saas.sh --dry-run           # 验证流程但不真推
```

**脚本效果**:
- Step 2 mirror push: saas-publish 仓会临时出现 community/ 46 文件
- Step 3 hotfix: 立即撤回 community/
- Step 4 验证: `0` 表示干净

### 3. 后续开发同步

```bash
# 本仓改完, 推到三个远端
git push origin main                            # 主仓 (GitHub Gobob-SOHO, 内部 monorepo)
./scripts/release_community.sh                 # Community (Apache-2.0 公开)
./scripts/release_saas.sh                      # SaaS (proprietary 私有)
```

> ⚠️ **不要直接 `git push origin main:remote/main`** — 会跳过 hotfix 撤回,泄露 SaaS / 社区版路径.
> ⚠️ **本仓改动后必须先 commit** — release 脚本会检查工作树干净.
> ⚠️ **SaaS 仓建议改为 private** — GitHub 当前默认是 public,任何人都能 clone 全部 saas/.

---

## Git History 残留泄露评估 (2026-09-17)

| 仓 | 状态 | 历史泄露评估 |
|----|------|------------|
| `Gobob-Soho-Community` (公开 Apache-2.0) | **有泄露** | commit `9e42294` ~ `d323877` 期间 (~10 分钟) 含 saas/ 49 文件 (13,486 行)<br>commit `64e683e` 已 hotfix 删除<br>**风险评估**: stars=0, forks=0, watchers=0, subscribers=0, 创建时间 2026-09-17 (几小时)<br>**实际访问者几乎为 0**, 但 GitHub git blob 永久保留, 任何 fork/clone 的人仍能拉到 |
| `Gobob-Soho-SaaS` (公开 Apache-2.0 待改 private) | 无敏感泄露 | 当前 main HEAD = `3221834`, 无 community/ 路径 (hotfix 已撤回) |

**剩余风险**: GitHub 公开 API 仍能拉到 commit `9e42294` 的 saas_admin.py + billing.py 完整内容. 降低风险的方案:
1. GitHub 仓库 Settings → Danger Zone → "Delete fork history" (只对 fork 生效, 对公开 commit 无效)
2. 联系 GitHub Support 申请从 git blob 中删除敏感文件 (高门槛, 通常拒绝)
3. 接受泄露 (因为 0 star + 0 fork + ~10 分钟窗口 + 仓库刚创建)
4. 让社区仓 private (跟 saas-publish 一样)

**当前选择**: 方案 3 — 接受泄露, GitHub 历史 blob 继续保留, 但未来严格用 release_*.sh 避免再次泄露.

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

**Last updated**: 2026-09-17 17:00 (cecilia + Claude, Portal 物理隔离 + P0 修复 saas 泄露 + release 流程重写)

**关键变更 (vs 上一版)**:
- `cloud/` → `saas/`(避免"cloud=闭源"的隐喻混淆)
- `community/app/` 与 `saas/app/` 物理隔离,brand 文案各自维护
- `community/portal/` 与 `saas/portal/` 物理隔离,Next.js 反代目标各自独立
- systemd unit (`gobob-soho-{backend,app,ops,portal}.service`) 全部指向 `saas/` 路径,不再用 community 代码兜底
- 发布脚本化:`scripts/release_community.sh` `scripts/release_saas.sh` 用 mirror push + post-push hotfix 撤回策略
- P0 事故已修复: 2026-09-17 16:30 commit 9e42294 曾把 saas/ 49 文件推到公开仓 ~10 分钟, hotfix 64e683e 撤回
- 后续 PM / cecilia 改 SaaS 走 saas/,改社区走 community/,**绝不允许跨边界混改**