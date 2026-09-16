# 部署指南

## 前置要求

- Docker + Docker Compose
- （可选）Gobob Data API Key — 见 [GETTING_GOBOB_API_KEY.md](GETTING_GOBOB_API_KEY.md)

## 快速开始

```bash
git clone https://github.com/GobobCore/Gobob-SOHO.git
cd Gobob-SOHO/deploy
cp ../.env.example ../.env   # 或直接放 deploy/.env
# 编辑 .env 填密码 / JWT secret / (可选) Gobob API Key
docker-compose up -d --build
```

> 注意：`docker-compose.yml` 在 `deploy/` 下，env 文件与它同目录读取，或通过 `../.env` 指定 `--env-file`。

## 服务与端口

| 端口 | 服务 | 说明 |
|---|---|---|
| 19001 | backend | FastAPI 业务 API（文档 `/docs`）|
| 19002 | portal | 获客门户（智能评估引流）|
| 19003 | app | 服务平台（机构端 + 学生/家长端）|
| 3306 | mysql | 数据库（容器内）|

## 首次启动

MySQL 容器首次启动自动执行 `backend/sql/schema.sql` + `seed.sql` 建表和种子。
backend 启动时自动创建初始机构和管理员（取 `.env` 的 `SOHO_ADMIN_USERNAME` / `SOHO_ADMIN_PASSWORD` / `SOHO_ORG_NAME`）。

登录 `http://localhost:19003`（服务平台）用初始管理员，开始：
1. 「员工管理」添加顾问
2. 「线索池」录入线索（或从获客门户留资自动进入）
3. 转化 → 签约 → 分配老师 → （可）换师

## 数据持久化

- MySQL 数据：`soho-mysql` volume
- 上传文件：`soho-files` volume

## 反向代理（生产）

建议用 Nginx/Caddy 把域名指到三个端口，例如：
- `portal.example.com` → 19002（对外获客）
- `app.example.com` → 19003（内部使用，可限制来源）

## 本地开发（不用 docker）

```bash
# 后端
cd backend && pip install -r requirements.txt
SOHO_MYSQL_HOST=... SOHO_MYSQL_PASS=... uvicorn main:app --port 19001

# 服务平台
cd app && python3 serve.py   # 19003，反代 /api → 19001

# 获客门户
cd portal && npm install && SOHO_BACKEND_URL=http://127.0.0.1:19001 npm run dev  # 19002
```

## 与 Gobob 主站联调（SMB API）

Gobob SOHO 的智能评估/院校数据由 Gobob 主站 `/api/smb/v1/*` 提供。

| 环境 | GOBOB_API_BASE | 说明 |
|---|---|---|
| 本机 dev | `http://127.0.0.1:18797` | 本机 Gobob backend（master 库） |
| tj0 生产 | `https://api.gobob.cn`（或 `http://<tj0-ip>:18797`） | 线上主站 |
| hk0 备用 | 同 tj0（只读副本） | 读操作走 hk0 replication，写（api_keys）只能 tj0 |

**API Key 管理**：
- 签发：`python3 backend/create_api_key_script.py`（见 `docs/SMB_API_DEPLOY.md` 主仓）
- 写操作（api_keys INSERT/UPDATE）只能在 **tj0 master** 执行；hk0 是 slave 只读副本
- 本机 dev 已签发：`gob_K0LxZjcv...IBL4`（含 6 个 smb scope）
- tj0 已签发：`gob_bEb4wl0aH_32paTInbRPmybngNVbRazX`

**Slave 只读兼容**：
- 主仓 `GOBOB_SKIP_MIGRATIONS=1` 环境变量：跳过 startup init + migration framework + api_key usage_count 更新
- 在 hk0 systemd unit 已设：`/etc/systemd/system/gobob-backend.service`
