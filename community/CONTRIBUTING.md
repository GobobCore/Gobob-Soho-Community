# Contributing to Gobob SOHO

Thank you for your interest in contributing! 🎉

Gobob SOHO is licensed under **Apache-2.0** (see [LICENSE](LICENSE)).
By contributing, you agree your contributions will be licensed under the same.

---

## Project structure

This is the **community edition** of Gobob SOHO. The repo has 3 top-level areas:

```
Gobob-SOHO/
├── shared/                # 业务核心 (本仓库所有改动 90% 在这里)
│   └── backend-core/
│       ├── api/           # 14 个业务路由
│       ├── core/          # 6 个基础模块
│       └── sql/           # schema/seed/migrations
├── community/             # 单机构版 (本仓库 GitHub 公开)
│   ├── backend/          # 入口 (85 路由, 无 SaaS)
│   ├── portal/           # Next.js 14
│   ├── app/              # Vue 3 SPA
│   └── deploy/
└── cloud/                # SaaS 闭源 (本仓库只 mirror, 实际在内部 Gitea)
```

**Rule of thumb**:
- 改业务核心 (leads/contracts/...) → 放 `shared/`
- 改开源版 UI (portal/app) → 放 `community/`
- 改 SaaS 多机构/计费/运营 → 放 `cloud/` (本仓只 mirror, 真正 PR 到内部 Gitea)

---

## How to contribute

### 1. 报告 Bug / 提需求

开 GitHub Issue, 模板:
- **Bug**: 复现步骤 + 期望/实际 + 截图/日志
- **Feature**: 需求场景 + 现有 workaround + 期望的 API/UI

### 2. 提 PR (代码改动)

```bash
# 1. fork + clone
git clone https://github.com/your-fork/Gobob-SOHO.git
cd Gobob-SOHO

# 2. 创建 feature 分支
git checkout -b feat/your-feature

# 3. 改动 (注意在 shared/ 还是 community/ 还是 cloud/)
# ... 改代码 ...

# 4. 跑后端测试 (后端改 business logic 才需要)
cd shared/backend-core
python3 -m pytest tests/  # 暂无, 跑 SQL 迁移 + 手动 E2E 即可

# 5. commit (按项目规范, 中文/英文都可, 描述改了什么 + 为什么)
git add -A
git commit -m "R-Feat: 新增 <功能> — <一句话>"

# 6. push + 开 PR
git push origin feat/your-feature
# 在 GitHub 开 PR, 填 description + 关联 issue
```

---

## Code style

- **Python**: PEP 8 + type hints, 跟 `backend/core/` 现有代码风格一致
- **TypeScript/React**: 项目已有 ESLint 配置 (`.eslintrc.json`), 跑 `npm run lint` 检查
- **Vue 3 (Options API)**: 跟 `app/index.html` + `js/views.js` 风格一致, 不用 Composition API (避免差异)
- **SQL**: 用 `IF NOT EXISTS / IF EXISTS` 保持迁移幂等
- **No emoji in code** (注释除外, 用 ❤️ 🤖 装饰 commit message OK)

### Commit message 规范

跟 Gobob 主仓一致:
```
R-Feat (2026-09-16): <一句话>  — 主仓格式
R-Fix (2026-09-16): <一句话>
R-Refactor (2026-09-16): <一句话>
R-Docs (2026-09-16): <一句话>
```

---

## 不要做的事

- ❌ 不要提交真实密码 / API Key / 数据库凭据
- ❌ 不要提交 `node_modules/` / `.venv/` / `*.tsbuildinfo` (已在 .gitignore)
- ❌ 不要改 `LICENSE` (Apache-2.0 不能改)
- ❌ 不要直接 push `cloud/` 改动到本仓库 PR (SaaS 闭源, PR 应到内部 Gitea)
- ❌ 不要在 PR 里塞多个无关的 commit (用 `git rebase -i` 整理)

---

## 拿到 Gobob Data API Key 测功能

社区版要测智能评估, 你需要一个 `gob_smb_...` Key:
1. 注册 https://www.gobob.cn
2. 申请 SMB Key (按次 ¥1 收费, 但有免费试用额度)
3. 填到 `.env` 的 `GOBOB_API_KEY`
4. 重启 `docker compose restart backend`

---

## 跑测试 / 验证

### Docker (推荐, 5 分钟)

```bash
cd community/deploy
cp ../.env.example .env
# 编辑 .env: 改 SOHO_ADMIN_PASSWORD / SOHO_MYSQL_PASS
docker compose up -d
# 等 30 秒
docker compose ps
# 应该 3 个服务都是 healthy
curl http://localhost:19011/api/health
# {"ok":true, ...}
```

### 本机裸机 (开发)

```bash
# 创建 venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r shared/backend-core/requirements.txt

# 启动 MySQL (用 docker 或本机)
docker run -d --name soho-mysql-test -e MYSQL_ROOT_PASSWORD=test \
  -e MYSQL_DATABASE=gobob_soho -e MYSQL_USER=soho -e MYSQL_PASSWORD=soho \
  -p 3306:3306 mysql:8

# 跑迁移 (按需)
mysql -h127.0.0.1 -usoho -psoho gobob_soho < shared/backend-core/sql/schema.sql
mysql -h127.0.0.1 -usoho -psoho gobob_soho < shared/backend-core/sql/seed.sql

# 启 backend
export SOHO_MYSQL_HOST=127.0.0.1
export SOHO_MYSQL_USER=soho
export SOHO_MYSQL_PASS=soho
export SOHO_MYSQL_DB=gobob_soho
export SOHO_JWT_SECRET=dev-secret-change-me
export SOHO_ADMIN_USERNAME=admin
export SOHO_ADMIN_PASSWORD=admin123
export SOHO_ORG_NAME=本地测试机构
export GOBOB_API_BASE=https://api.gobob.cn  # 或本机 18797
export GOBOB_API_KEY=gob_your_key_here

uvicorn community.backend.main:app --host 0.0.0.0 --port 19011 --reload
```

---

## 报告安全问题

发现安全漏洞? **不要开公开 Issue**.
发邮件到: security@gobob.cn

我们会在 24h 内响应, 修好后再公开 CVE.

---

## License 共识

By submitting a PR, you agree:
- 你的贡献以 Apache-2.0 发布
- 你有合法权利贡献这些代码 (不是从私有代码抄的)
- 贡献者列表会加到 README (可选)

Thanks for making Gobob SOHO better! 🚀
