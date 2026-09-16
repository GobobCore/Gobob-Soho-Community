# 仓库策略说明 (SaaS 闭源 vs 开源社区版)

> **日期**: 2026-09-16 · **起草**: cecilia
> **关联**: SPLIT_PLAN_SAAS_VS_COMMUNITY_2026-09-16.md, 拆分规划 §1 方案

---

## TL;DR

**主仓 `GobobCore/Gobob-SOHO` 就是开源版。** 不再开独立 repo。
SaaS 闭源部分在本地 `cloud/` (Gitea 内部), 不上 GitHub。

---

## 为什么不开独立社区版 repo

**Plan §1 提到的 3 个方案**, 最后选的是「单 repo + 目录拆分」:
- `shared/` — 业务核心, 社区版和 SaaS 版共用
- `community/` — 开源版 (推到 GitHub)
- `cloud/` — SaaS 闭源 (本地 + Gitea)

**Phase 4.2 重新考虑**: 既然 `community/` 目录已经清晰隔离在主仓, **不需要再 split 独立 repo**。

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 主仓 `GobobCore/Gobob-SOHO` 单仓含社区版 | 维护成本低, SaaS 和社区版 commit 同步 | 主仓含 SaaS 痕迹(虽然 .gitignore 阻了 cloud/) | ✅ **当前采用** |
| 独立 repo `GobobCore/Gobob-SOHO-Community` | 社区版 0 SaaS 痕迹 | 业务核心必须双子目录, 维护成本高 | ❌ 暂不做 |
| 双 repo + submodule | 同上 | submodule 调试麻烦 | ❌ 不推荐 |

**关键理由**:
1. `cloud/` 已加 .gitignore, GitHub 公开版里**完全没有 SaaS 闭源代码** ✅
2. `shared/` 业务核心两版共用, 同 commit 同步, **避免双子目录漂移**
3. PM 未来想 SaaS 私有仓独立时, 用 `git subtree split` 30 秒就能拆出去
4. 文档清晰 (`docs/SPLIT_PLAN_*.md` + `community/README.md`), 用户一眼就懂

---

## 社区版用户怎么用

社区版用户从 GitHub clone 主仓:

```bash
git clone https://github.com/GobobCore/Gobob-SOHO.git
cd Gobob-SOHO
# 1) 装依赖
cd shared/backend-core && pip install -r requirements.txt
cd ../..
# 2) 跑 migration
cd community/deploy
docker compose up -d
# 3) 默认 19011 (backend) / 19012 (portal) / 19013 (app)
```

详细看 [community/README.md](community/README.md) (已重写, 区分社区版 vs SaaS, 含 docker + 裸机两套部署)。

---

## 未来如何真正独立

PM 后面想 100% 独立 repo, 30 秒拆:

```bash
# 1. PM 在 GitHub 端手动建 GobobCore/Gobob-SOHO-Community (public, Apache-2.0)
# 2. 跑我们准备好的脚本:
bash scripts/push_community_subtree.sh
# (脚本里调 git subtree push --prefix=community git@github.com:GobobCore/Gobob-SOHO-Community.git main)
# 3. shared/ 不在 split 里, 社区版需要的代码会在 subtree push 时自动复制
# 4. 之后每次 community/ 改动, 同步: 同上 git subtree push 命令
```

或者更简单: 用 `git subtree add` 把 shared 复制进去, 定期从主仓 pull。

---

## Phase 4.2 关闭

本 task (`Phase 4.2 git subtree split community`) **最终不做独立 repo**, 改为"加强 README 指引"。
状态: 实质完成 (社区版已通过 GitHub `GobobCore/Gobob-SOHO` 公开)。
