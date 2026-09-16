# SOHO 本机 5 分钟 quickstart

> **给**: 想在本机跑起来看效果的机构 / 开发者
> **假设**: 已有 MySQL 8 + Python 3.11+ + Node 20+
> **不适合**: 生产部署 → 用 [DEPLOY.md](DEPLOY.md) 的 docker 方式

---

## 1. 克隆 + 准备

```bash
git clone https://github.com/GobobCore/Gobob-SOHO.git
cd Gobob-SOHO
```

## 2. 建库

```bash
mysql -uroot -p <<'SQL'
CREATE DATABASE gobob_soho CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'soho'@'localhost' IDENTIFIED BY 'choose-a-password';
GRANT ALL ON gobob_soho.* TO 'soho'@'localhost';
FLUSH PRIVILEGES;
SQL

mysql -usoho -p gobob_soho < backend/sql/schema.sql
mysql -usoho -p gobob_soho < backend/sql/seed.sql
```

## 3. 起 backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 设环境变量 (最小集)
export SOHO_MYSQL_HOST=127.0.0.1
export SOHO_MYSQL_USER=soho
export SOHO_MYSQL_PASS=choose-a-password
export SOHO_MYSQL_DB=gobob_soho
export SOHO_JWT_SECRET=$(openssl rand -hex 32)
export SOHO_ADMIN_USERNAME=admin
export SOHO_ADMIN_PASSWORD=admin123    # 上生产务必改
export SOHO_ORG_NAME=我的留学工作室

# 可选: 接 Gobob 智能评估 (不要也能跑核心)
export GOBOB_API_BASE=https://api.gobob.cn
export GOBOB_API_KEY=gob_your_key     # 见 GETTING_GOBOB_API_KEY.md

uvicorn main:app --port 19001
# 验证: curl http://127.0.0.1:19001/api/health
```

## 4. 起 portal (获客门户, 19002)

```bash
cd ../portal
npm install && npm run build
SOHO_BACKEND_URL=http://127.0.0.1:19001 npm start
# 访问 http://localhost:19002
```

## 5. 起 app (服务平台, 19003)

```bash
cd ../app
SOHO_BACKEND=http://127.0.0.1:19001 SOHO_APP_PORT=19003 python3 serve.py
# 访问 http://localhost:19003, 用 admin/admin123 登录
```

## 6. 验证

```bash
# 获客门户 — 匿名智能评估
open http://localhost:19002/assessment

# 服务平台 — 登录后看驾驶舱 / 线索 / 学生
open http://localhost:19003

# 后端 API 文档
open http://localhost:19001/docs
```

---

## 下一步

- **想长期跑**: 改成 systemd 管理 — 见 [DEPLOY_LOCAL_SYSTEMD.md](DEPLOY_LOCAL_SYSTEMD.md)
- **想部署生产**: docker — 见 [DEPLOY.md](DEPLOY.md)
- **想接 Gobob 数据**: 申请 API Key — 见 [GETTING_GOBOB_API_KEY.md](GETTING_GOBOB_API_KEY.md)
- **看 API 细节**: [API.md](API.md)
- **看所有配置**: [CONFIG.md](CONFIG.md)
