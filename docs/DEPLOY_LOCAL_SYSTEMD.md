# 本机裸机部署 (systemd, 无 docker)

> **适用场景**: 开发者本机 / 内部测试机, 不想起 docker 容器
> **当前环境**: gobob 主仓同机 (192.168.1.5), 3 个 systemd --user service

跟 `DEPLOY.md` 的 docker 方式并行, 这份文档记录**本机 19001/19002/19003 直接由 systemd 管理**的实际部署经验。

---

## 架构

```
┌────────────────────────────────────────────────────────┐
│  systemd --user (linger=yes, 开机自起)                  │
│                                                         │
│  gobob-soho-backend.service   19001   FastAPI           │
│  gobob-soho-portal.service    19002   Next.js 14        │
│  gobob-soho-app.service       19003   Vue 3 SPA + proxy │
└────────────────────────────────────────────────────────┘
         │                    │                  │
         └────────────────────┴──────────────────┘
                              │
                    gobob-backend (18797) SMB API
                              │
                    MySQL gobob_soho 库 (共用本机 3306)
```

---

## 文件位置

```
~/.config/systemd/user/gobob-soho-backend.service
~/.config/systemd/user/gobob-soho-portal.service
~/.config/systemd/user/gobob-soho-app.service

~/.openclaw/workspace/gobob-soho/
├── backend/   (FastAPI, uvicorn 跑在 /tmp/soho-venv)
├── portal/    (Next.js, npm start, node_modules 已装)
└── app/       (Vue 3 SPA, python3 serve.py)
```

---

## 一、backend (19001)

`gobob-soho-backend.service`:

```ini
[Unit]
Description=Gobob SOHO backend (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ricky/.openclaw/workspace/gobob-soho/backend
Environment="SOHO_MYSQL_HOST=127.0.0.1"
Environment="SOHO_MYSQL_USER=soho"
Environment="SOHO_MYSQL_PASS=SohoTest#2026x"
Environment="SOHO_MYSQL_DB=gobob_soho"
Environment="SOHO_JWT_SECRET=testsecret0123456789abcdef0123456789abcdef"
Environment="SOHO_ADMIN_USERNAME=admin"
Environment="SOHO_ADMIN_PASSWORD=Admin#2026x"
Environment="SOHO_ORG_NAME=E2E测试留学工作室"
Environment="GOBOB_API_BASE=http://127.0.0.1:18797"
Environment="GOBOB_API_KEY=gob_xxx"  # 用 Gobob 主仓创建的 SMB Key
ExecStart=/tmp/soho-venv/bin/uvicorn main:app --host 0.0.0.0 --port 19001
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

**首次准备**:

```bash
# 1. venv
python3 -m venv /tmp/soho-venv
source /tmp/soho-venv/bin/activate
pip install -r ~/.openclaw/workspace/gobob-soho/backend/requirements.txt

# 2. MySQL 库 + 用户 (用本机 root 跑一次)
mysql -uroot -p <<'SQL'
CREATE DATABASE IF NOT EXISTS gobob_soho CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'soho'@'localhost' IDENTIFIED BY 'SohoTest#2026x';
GRANT ALL PRIVILEGES ON gobob_soho.* TO 'soho'@'localhost';
FLUSH PRIVILEGES;
SQL

# 3. 建表 + 种子
mysql -usoho -pSohoTest#2026x gobob_soho < ~/.openclaw/workspace/gobob-soho/backend/sql/schema.sql
mysql -usoho -pSohoTest#2026x gobob_soho < ~/.openclaw/workspace/gobob-soho/backend/sql/seed.sql

# 4. 起服务
systemctl --user daemon-reload
systemctl --user enable --now gobob-soho-backend
```

**验证**:

```bash
curl http://127.0.0.1:19001/api/health
# {"ok":true,"service":"gobob-soho","db":"up","gobob_data_api":"configured"}
```

---

## 二、portal (19002)

`gobob-soho-portal.service`:

```ini
[Unit]
Description=Gobob SOHO portal frontend (Next.js assessment lead-gen)
After=network.target gobob-soho-backend.service

[Service]
Type=simple
WorkingDirectory=/home/ricky/.openclaw/workspace/gobob-soho/portal
Environment="SOHO_BACKEND_URL=http://127.0.0.1:19001"
Environment="PORT=19002"
Environment="NODE_ENV=production"
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

**首次准备**:

```bash
cd ~/.openclaw/workspace/gobob-soho/portal
npm install
npm run build  # 生成 .next/

systemctl --user daemon-reload
systemctl --user enable --now gobob-soho-portal
```

**验证**:

```bash
curl -I http://127.0.0.1:19002/             # HTTP 200
curl -I http://127.0.0.1:19002/assessment   # HTTP 200
curl http://127.0.0.1:19002/api/assessment/meta | head -c 200  # 反代 backend 通
```

---

## 三、app (19003)

`gobob-soho-app.service`:

```ini
[Unit]
Description=Gobob SOHO service platform frontend (Vue3 SPA + proxy)
After=network.target gobob-soho-backend.service

[Service]
Type=simple
WorkingDirectory=/home/ricky/.openclaw/workspace/gobob-soho/app
Environment="SOHO_BACKEND=http://127.0.0.1:19001"
Environment="SOHO_APP_PORT=19003"
ExecStart=/usr/bin/python3 serve.py
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

**首次准备**:

```bash
# 无依赖, 直接起
systemctl --user daemon-reload
systemctl --user enable --now gobob-soho-app
```

**验证**:

```bash
curl -I http://127.0.0.1:19003/          # HTTP 200
curl http://127.0.0.1:19003/api/health   # 反代 backend 通
```

---

## 常用命令

```bash
# 状态
systemctl --user status gobob-soho-backend gobob-soho-portal gobob-soho-app

# 重启某个
systemctl --user restart gobob-soho-backend

# 全部重启
systemctl --user restart gobob-soho-backend gobob-soho-portal gobob-soho-app

# 看日志
journalctl --user -u gobob-soho-backend -n 50 --no-pager
journalctl --user -u gobob-soho-portal -f

# 关停
systemctl --user stop gobob-soho-portal
```

---

## 默认账号

- **服务平台 (19003)**: admin / Admin#2026x (见 backend service env `SOHO_ADMIN_*`)
- **机构**: E2E测试留学工作室
- **获客门户 (19002)**: 匿名可用, 留资自动进 leads

---

## 与 Gobob 主仓的依赖

| 依赖 | 用途 | 故障影响 |
|---|---|---|
| Gobob backend 18797 `/api/smb/v1/*` | 智能评估 / 院校数据 | 仅评估和院校下拉不可用, 核心业务不影响 |
| 本机 MySQL 3306 | gobob_soho 库 | 全站挂 |

**Gobob 侧 SMB Key 管理**: 用 Gobob admin token 调 `POST /api/api-keys` 创建, 写进 `GOBOB_API_KEY` env。当前生产 Key: id=39 `Gobob-SOHO-本机部署`。

---

## 跟 docker 部署的差别

| 维度 | docker | 本机 systemd |
|---|---|---|
| 隔离 | 容器 | 进程级 |
| MySQL | 独立容器 | 共用本机 3306 |
| 端口冲突 | 无 | 要避开 gobob 全家桶 18797-18807 |
| 备份 | volume 单独 | 跟本机 mysql 一起 mysqldump |
| 升级 | docker pull + rebuild | git pull + restart |

---

**Last updated**: 2026-09-16 (cecilia, 跟着实际部署过程写)
