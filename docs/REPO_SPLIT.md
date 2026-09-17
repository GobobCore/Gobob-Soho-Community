# Gobob SOHO 三仓拆分说明 (R-Refactor 2026-09-17)

> **本仓 (Gobob-SOHO)** 是开发 monorepo, 含 shared/ + community/ + cloud/ 三层。
> Release 时用 subtree split 推到两个独立 GitHub repo (Community 公开 + SaaS 私有)。

---

## 三仓分工

| 仓 | 内容 | License | GitHub URL | 端口 |
|---|---|---|---|---|
| **`Gobob-SOHO`** (本仓, monorepo) | 全部三层, 开发用 | (内部, 不发布) | intsch Gitea | — |
| **`Gobob-Soho-Community`** | community/ + shared/ (扁平) | Apache-2.0 | github.com/GobobCore/Gobob-Soho-Community | 19011/19012/19013 |
| **`Gobob-Soho-SaaS`** | cloud/ + shared/ (扁平) | proprietary (private) | github.com/GobobCore/Gobob-Soho-SaaS | 19001/19002/19003/19004 |

---

## 拆分流程 (release 时)

### 1. 拆分社区版 → 推 Community repo

```bash
cd /home/ricky/.openclaw/workspace/gobob-soho

# 1.1 创建独立分支 (clean 历史, 只含 community/ 改动)
git subtree split --prefix=community --annotate="(community)" -b community-only

# 1.2 加 shared/ (复制 main 仓根目录的 shared/ 到 community-only 根)
git checkout community-only
git checkout main -- shared/  # 拷贝 shared 到 community-only 根

# 1.3 调整路径: community/ 提到根 (subtree split 已做)
#      backend/main.py  路径调整 (community/backend → backend)
#      deploy/Dockerfile.* 路径调整
#      .env.example 端口 19001/02/03 → 19011/12/13
#      README 指向 Community repo
#      .gitignore 加 community/ + cloud/ 保护

# 1.4 commit + push
git add -A
git commit -m "R-Refactor: 拆分到独立 repo — community 版扁平化 + shared/ 内嵌"
git remote add community-publish git@github.com:GobobCore/Gobob-Soho-Community.git
git push community-publish community-only:main --force
```

### 2. 拆分 SaaS → 推 SaaS repo

```bash
# 2.1 cloud/ 在 .gitignore 里, git subtree split 找不到 → 用 orphan 分支手动 cp
git checkout --orphan saas-publish
mkdir -p backend/api tests soho-ops/js
cp cloud/backend-saas/main.py backend/main.py
cp cloud/backend-saas/api/saas_admin.py backend/saas_admin.py
cp cloud/backend-saas/api/billing.py backend/billing.py
cp cloud/backend-saas/api/__init__.py backend/api/__init__.py
cp cloud/backend-saas/tests/test_billing_logic.py tests/test_billing_logic.py
cp cloud/soho-ops/* soho-ops/
cp cloud/soho-ops/js/* soho-ops/js/
cp -r shared .   # 共享业务核心

# 2.2 写 SaaS 专属配置
cat > .env.example << 'EOF'
# SaaS 端口 19001/02/03/04 (跟社区版区分)
SOHO_BACKEND_PORT=19001
SOHO_PORTAL_PORT=19002
SOHO_APP_PORT=19003
SOHO_OPS_PORT=19004
# ... 见仓库内 .env.example
EOF

# 2.3 commit + push
git add -A
git commit -m "Initial: Gobob SOHO SaaS Edition — 独立 repo 拆分"
git remote add saas-publish git@github.com:GobobCore/Gobob-Soho-SaaS.git
git push saas-publish saas-publish:main --force
```

### 3. 后续开发同步

```bash
# 本仓改完, 推到两个独立 repo
git push origin main                                       # 主仓 (intsch Gitea)
git push community-publish community-only:main --force     # Community
git push saas-publish saas-publish:main --force            # SaaS
```

> 注: 实际生产用 GitHub Actions 自动跑 split + push, 不用每次手动。

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

**Last updated**: 2026-09-17 (cecilia, 三仓拆分完成)