# SOHO 社区版 — 本机 5 分钟 quickstart

> **给**: 想在本机跑起来看效果的机构 / 开发者
> **假设**: 已有 MySQL 8 + Python 3.11+ + Node 20+
> **不适合**: 生产部署 → 用 [DEPLOY.md](DEPLOY.md) 的 docker 方式
>
> ⚠️ **R-Refactor (2026-09-16) 仓库拆分后**: 业务核心在 `shared/backend-core/`,社区版入口在 `community/backend/`,前端在 `community/portal` + `community/app`。
> 默认端口 19011/19012/19013 (避开 SaaS 19001/19002/19003 + Gobob 主站 18797~18807)。

---

## 1. 克隆 + 准备

```bash
git clone https://github.com/GobobCore/Gobob-SOHO.git
cd Gobob-SOHO
```

## 2. Python 虚拟环境 + 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r shared/backend-core/requirements.txt
```

## 3. 建库 (MySQL)

```bash
mysql -uroot -p <<'SQL'
CREATE DATABASE IF NOT EXISTS gobob_soho CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'soho'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL ON gobob_soho.* TO 'soho'@'localhost';
FLUSH PRIVILEGES;
SQL
```

## 4. 跑迁移 (建表 + 种子)

```bash
mysql -usoho -p gobob_soho < shared/backend-core/sql/schema.sql
mysql -usoho -p gobob_soho < shared/backend-core/sql/seed.sql
```

## 5. 起 backend (FastAPI, 19011)

```bash
export SOHO_MYSQL_HOST=127.0.0.1
export SOHO_MYSQL_USER=soho
export SOHO_MYSQL_PASS=choose-a-password
export SOHO_MYSQL_DB=gobob_soho
export SOHO_JWT_SECRET=$(openssl rand -hex 32)
export SOHO_ADMIN_USERNAME=admin
export SOHO_ADMIN_PASSWORD=admin123        # 上生产务必改
export SOHO_ORG_NAME=我的留学工作室

# 可选: 接 Gobob 智能评估 (不要也能跑核心业务)
export GOBOB_API_BASE=https://api.gobob.cn
export GOBOB_API_KEY=gob_smb_your_key      # 见 GETTING_GOBOB_API_KEY.md

uvicorn community.backend.main:app --host 0.0.0.0 --port 19011 --reload
# 验证: curl http://127.0.0.1:19011/api/health
```

## 6. 起 portal (获客门户, 19012)

```bash
cd community/portal
npm install
npm run dev          # 开发; 生产用 npm run build && npm start
# 访问 http://localhost:19012
```

## 7. 起 app (服务平台, 19013)

```bash
cd ../app
SOHO_BACKEND=http://127.0.0.1:19011 python3 serve.py
# 访问 http://localhost:19013, 用 admin/admin123 登录
```

## 8. 验证

```bash
# 1. 后端健康
curl http://127.0.0.1:19011/api/health
# 期望: {"ok":true,"service":"gobob-soho","db":"up","gobob_data_api":"..."}

# 2. 登录拿 token
curl -X POST http://127.0.0.1:19011/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -m json.tool

# 3. 浏览器访问
open http://localhost:19012       # 获客门户 (匿名智能评估)
open http://localhost:19013       # 服务平台 (admin/admin123)
open http://localhost:19011/docs   # API 文档 (Swagger)
```

---

## 故障排查

| 问题 | 解决 |
|---|---|
| `Connection refused` on 19011 | MySQL 没启, 或 `SOHO_MYSQL_HOST` 写错 |
| `ModuleNotFoundError: community` | 没装 requirements / 不在 venv / cwd 不是 repo 根 |
| 评估 502 | 没设 `GOBOB_API_BASE` 或 API Key, 智能评估会失败 (其他功能正常) |
| 端口被占 | backend 改 `--port 19015`, 同步改 portal/app 的 `SOHO_BACKEND_URL` |
| portal `npm run dev` 报端口 19012 占用 | `PORT=19015 npm run dev` 然后改 portal 反代 backend URL |

---

## 跟 docker 部署的差别

| 维度 | 本机裸机 (本文) | docker (DEPLOY.md) |
|---|---|---|
| 隔离 | 进程级 | 容器 |
| MySQL | 共用本机 3306 | 独立容器 + volume |
| 启动 | 手动跑 3 个进程 | `docker compose up -d` |
| 适合 | 开发者调试 | 生产/多机部署 |

---

## 下一步

- **想长期跑**: 改成 systemd 管理 — 见 [DEPLOY_LOCAL_SYSTEMD.md](DEPLOY_LOCAL_SYSTEMD.md)
- **想部署生产**: docker 一键起 — 见 [DEPLOY.md](DEPLOY.md)
- **想接 Gobob 数据**: 申请 API Key — 见 [GETTING_GOBOB_API_KEY.md](GETTING_GOBOB_API_KEY.md)
- **看 API 细节**: [API.md](API.md)
- **看所有配置**: [CONFIG.md](CONFIG.md)
- **想理解拆分架构**: [SPLIT_PLAN_SAAS_VS_COMMUNITY_2026-09-16.md](SPLIT_PLAN_SAAS_VS_COMMUNITY_2026-09-16.md)

---

**Last updated**: 2026-09-17 (cecilia, 对齐 shared/community 三层重构 + 19011/19012/19013 端口)