# CI Secrets 配置 (GitHub Actions)

> **维护者**: cecilia + PM
> **更新触发**: secrets 变更 / workflow 新增 job 时
> **用途**: 指引 GitHub 仓库 Settings → Secrets 配置

---

## 为什么需要 Secrets

GitHub Actions 推代码到 `Gobob-Soho-Community` 和 `Gobob-Soho-SaaS` 远端仓需要 SSH key 鉴权。用 GitHub Secrets 安全注入,不在 workflow 文件或 logs 里明文出现。

---

## Secrets 清单

| Secret 名 | 用途 | 配置方法 |
|-----------|------|----------|
| **`SOHO_DEPLOY_SSH_KEY`** | 推送到 Community / SaaS 远端仓的 SSH private key | `cat ~/.ssh/id_xxx` 内容粘贴 (整段含 `-----BEGIN...-----` 头尾) |
| (可选) `PM_TRIGGER_TOKEN` | 防外部人乱触发 workflow_dispatch | 暂未启用, 预留 |

### 不在 Secrets 里的

| 项 | 处理 |
|---|---|
| `MINIMAX_API_KEY`, `DEEPSEEK_API_KEY` | 永远不放 secrets, 也不放 systemd, 改用 OpenClaw SecretRefs |
| `GOBOB_MYSQL_PASS` | 同上 |
| `GOBOB_API_KEY` (gob_smb_xxx) | 在 release 脚本中已被 audit 标记为禁推, 但生产部署时仍在 systemd unit (待迁 SecretRefs) |

---

## 生成 deploy SSH key 步骤

```bash
# 1. 在本机生成专用 deploy key (跟个人 SSH key 分离)
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/soho_deploy

# 2. 复制公钥到 3 个 GitHub 仓的 Deploy keys
#    (Settings → Deploy keys → Add deploy key → 勾选 Allow write access)
cat ~/.ssh/soho_deploy.pub
# Gobob-SOHO (monorepo)
# Gobob-Soho-Community
# Gobob-Soho-SaaS

# 3. 复制私钥到 Gobob-SOHO 仓的 Secrets
cat ~/.ssh/soho_deploy
# Settings → Secrets and variables → Actions → New repository secret
# Name: SOHO_DEPLOY_SSH_KEY
# Value: <粘贴整段私钥内容>
```

---

## Workflow 触发方式

### 方式 1: 手动触发 (推荐, 默认)

GitHub repo → Actions → Release SOHO → Run workflow → 选输入 → Run

```
target     = community / saas / both (默认 both)
dry_run    = true / false (默认 true, 一定要显式改 false + confirm 才真推)
confirm    = (留空 = 不推, 填 "yes" / 任意文本 = 允许推)
```

**安全**: 即使选 dry_run=false, 没填 confirm 也不会推。双重保护。

### 方式 2: 周更 cron (审计 only)

每周一北京时间 02:00 跑一次,只做 audit 不真推:

```yaml
schedule:
  - cron: "0 18 * * 0"   # UTC 周日 18:00 = 北京周一 02:00
```

这个 cron 触发的 workflow 走 dry_run 逻辑,只扫 audit 不真推。

---

## 验证 Workflow

推送 release.yml 后:

```bash
git push origin main
# GitHub repo → Actions 标签 → 看到 Release SOHO workflow
# 手动 Run workflow → dry_run=true → Run → 等 1-2 分钟
# 看 logs: 应有 audit step 通过, release_community.sh dry-run 不真推
```

---

## 失败处理

如果 workflow 失败,会自动创建 GitHub Issue (label `release-failure`) 包含:

- Workflow 名 + Run 号
- 触发人
- Run URL
- 提示人工 review (audit / hotfix / 远端仓)

人工处理:
1. 看 GitHub Actions logs
2. 如果是 audit 失败: 检查新增代码是否含敏感信息, 修复后重跑
3. 如果是 release 失败: 检查远端仓状态, 可能要手动 hotfix

---

## 已知坑

1. **GH Actions runner 默认无 SSH key**: 必须配 `SOHO_DEPLOY_SSH_KEY` secret + 用 `webfactory/ssh-agent` action 加载
2. **GitHub 默认工作流权限是 read-only**: 推送到远端仓需要 workflow 有 write 权限 — Settings → Actions → General → Workflow permissions → "Read and write permissions"
3. **workflow_dispatch 没有 `github.event.inputs` 在 schedule 触发时**: workflow 用了 `if` 条件避免 schedule 时尝试读 inputs
4. **hotfix step 失败会留垃圾**: release_*.sh 的 hotfix step 如果 push 失败, 会在 monorepo 留临时分支; `git branch -D` 会清理,但远程分支需要手动删

---

## 本地等效流程 (不走 CI)

如果 GitHub Actions 不可用, 可以本地跑:

```bash
cd /home/ricky/.openclaw/workspace/gobob-soho

# Dry-run (不真推)
./scripts/release_community.sh --dry-run
./scripts/release_saas.sh --dry-run

# 实际推送
./scripts/release_community.sh
./scripts/release_saas.sh
```

CI 跟本地的差异: CI 跑在干净的 ubuntu-latest runner 上, 本地可能有 untracked 文件 / uncommitted changes. CI 默认 dry-run=true 强制先看输出再确认。

---

**Last updated**: 2026-09-17 17:30 (cecilia + Claude, GitHub Actions 自动 release 上线)