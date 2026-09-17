# 部署指南 (Docker)

> **R-Refactor (2026-09-16)**: docker-compose 已迁移到 `community/deploy/`,路径/端口都换了。
> **当前部署根**: `community/deploy/docker-compose.yml`,默认端口 **19011/19012/19013**。
>
> ⚠️ 本文档记录的是**社区版** docker 部署。SaaS 版在 `cloud/deploy-saas/`,端口 19001/19002/19003。

---

## 前置要求

- Docker + Docker Compose
- （可选）Gobob Data API Key — 见 [GETTING_GOBOB_API_KEY.md](GETTING_GOBOB_API_KEY.md)

## 快速开始

```bash
git clone https://github.com/GobobCore/Gobob-SOHO.git
cd Gobob-SOHO/community/deploy

# 准备 env (从 example 复制)
cp ../.env.example .env
# 编辑 .env 填密码 / JWT secret / (可选) Gobob API Key

docker compose up -d --build
# 等 30 秒: MySQL 自动跑 schema + seed, backend 自动启动
```

## 服务与端口 (社区版)

| 端口 | 服务 | 说明 |
|---|---|---|
| **19011** | backend | FastAPI 业务 API (文档 `/docs`) |
| **19012** | portal | 获客门户 (Next.js, 智能评估引流) |
| **19013** | app | 服务平台 (Vue 3 SPA, 机构端 + 学生/家长端) |
| 3306 | mysql | 数据库 (容器内, 暴露到本机 3307 防冲突) |

> 选 1901x 段是为了避开 SaaS 1900x + Gobob 主站 18797~18807。
> 端口可通过 `SOHO_BACKEND_PORT` / `SOHO_PORTAL_PORT` / `SOHO_APP_PORT` 覆盖。

## 首次启动

MySQL 容器首次启动**自动执行**:
- `shared/backend-core/sql/schema.sql` (建表)
- `shared/backend-core/sql/seed.sql` (种子)

backend 启动时自动创建初始机构和管理员(取 `.env` 的 `SOHO_ADMIN_USERNAME` / `SOHO_ADMIN_PASSWORD` / `SOHO_ORG_NAME`)。

登录 `http://localhost:19013`(服务平台)用初始管理员,开始:
1. 「员工管理」添加顾问
2. 「线索池」录入线索(或从获客门户留资自动进入)
3. 转化 → 签约 → 分配老师 → (可)换师

## 数据持久化

- MySQL 数据: `soho-mysql` volume
- 上传文件: `soho-files` volume

## 反向代理(生产)

建议用 Nginx/Caddy 把域名指到三个端口,例如:
- `portal.example.com` → 19012(对外获客)
- `app.example.com` → 19013(内部使用,可限制来源)
- `api.example.com` → 19011(API 文档,可限内网)

## 本地开发(不用 docker)

见 [QUICKSTART_LOCAL.md](QUICKSTART_LOCAL.md) 或 [community/QUICKSTART.md](../community/QUICKSTART.md):

```bash
# 后端 (community/backend/main.py 入口)
python3 -m venv .venv && source .venv/bin/activate
pip install -r shared/backend-core/requirements.txt
SOHO_MYSQL_HOST=127.0.0.1 SOHO_MYSQL_PASS=... \
  uvicorn community.backend.main:app --port 19011 --reload

# 服务平台
cd community/app && SOHO_BACKEND=http://127.0.0.1:19011 python3 serve.py   # 19013

# 获客门户
cd community/portal && npm install && SOHO_BACKEND_URL=http://127.0.0.1:19011 npm run dev   # 19012
```

## 与 Gobob 主站联调(SMB API)

Gobob SOHO 的智能评估/院校数据由 Gobob 主站 `/api/smb/v1/*` 提供。

| 环境 | GOBOB_API_BASE | 说明 |
|---|---|---|
| 本机 dev | `http://127.0.0.1:18797` | 本机 Gobob backend(master 库) |
| tj0 生产 | `https://api.gobob.cn`(或 `http://<tj0-ip>:18797`) | 线上主站 |
| hk0 备用 | 同 tj0(只读副本) | 读操作走 hk0 replication,写(api_keys)只能 tj0 |

**API Key 管理**:
- 签发: 用 Gobob admin token 调 `POST /api/api-keys`,scope 用 `smb:*`
- 写操作(api_keys INSERT/UPDATE)只能在 **tj0 master** 执行;hk0 是 slave 只读副本
- 本机 dev 已签发示例: `gob_K0LxZjcv...IBL4`(含 6 个 smb scope)

**Slave 只读兼容**:
- 主仓 `GOBOB_SKIP_MIGRATIONS=1` 环境变量:跳过 startup init + migration framework + api_key usage_count 更新
- 在 hk0 systemd unit 已设: `/etc/systemd/system/gobob-backend.service`

## 仓库拆分说明 (R-Refactor 2026-09-16)

```
Gobob-SOHO/
├── shared/backend-core/    # 业务核心 (社区版 + SaaS 共用)
├── community/              # 开源版 (本指南)
│   ├── backend/main.py     # 社区版入口
│   ├── portal/             # 获客门户
│   ├── app/                # 服务平台
│   └── deploy/             # ← 本文档的 docker-compose 在这里
└── cloud/                  # SaaS 闭源 (本地 Gitea, 不上 GitHub)
```

SaaS 版部署在 `cloud/deploy-saas/`,独立端口 19001/19002/19003,不在 GitHub 公开版里。

---

**Last updated**: 2026-09-17 (cecilia, 对齐 shared/community 三层重构 + 19011/19012/19013)