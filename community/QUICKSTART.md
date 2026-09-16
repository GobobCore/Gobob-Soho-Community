# 社区版 5 分钟 quickstart (本机裸机, 不用 Docker)

> 适合: 开发者本地跑、PoC、生产环境 docker 之外的方案
> 走 docker 的见 [deploy/docker-compose.yml](deploy/docker-compose.yml)

## 1. 准备 (1 分钟)

```bash
# 假设你已经 clone 了 Gobob-SOHO 仓库
cd Gobob-SOHO

# Python 3.11+ (后端)
python3 -m venv .venv
source .venv/bin/activate
pip install -r shared/backend-core/requirements.txt
```

## 2. MySQL (2 分钟)

```bash
# 选项 A: 用本机 MySQL
mysql -uroot -p <<'SQL'
CREATE DATABASE gobob_soho CHARACTER SET utf8mb4;
CREATE USER 'soho'@'localhost' IDENTIFIED BY 'soho';
GRANT ALL ON gobob_soho.* TO 'soho'@'localhost';
FLUSH PRIVILEGES;
SQL

# 选项 B: 用 docker 跑个一次性 MySQL
docker run -d --name soho-mysql \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=gobob_soho \
  -e MYSQL_USER=soho -e MYSQL_PASSWORD=soho \
  -p 3306:3306 mysql:8
```

## 3. 跑迁移 (1 分钟)

```bash
mysql -h127.0.0.1 -usoho -psoho gobob_soho < shared/backend-core/sql/schema.sql
mysql -h127.0.0.1 -usoho -psoho gobob_soho < shared/backend-core/sql/seed.sql
```

## 4. 启动 backend (1 分钟)

```bash
export SOHO_MYSQL_HOST=127.0.0.1
export SOHO_MYSQL_USER=soho
export SOHO_MYSQL_PASS=soho
export SOHO_MYSQL_DB=gobob_soho
export SOHO_JWT_SECRET=dev-secret-change-me-in-prod
export SOHO_ADMIN_USERNAME=admin
export SOHO_ADMIN_PASSWORD=admin123
export SOHO_ORG_NAME=本地测试机构
export GOBOB_API_BASE=https://api.gobob.cn
# export GOBOB_API_KEY=gob_your_key_here  # 可选, 没 Key 也能跑核心业务

# 跑 backend (19011)
uvicorn community.backend.main:app --host 0.0.0.0 --port 19011 --reload
```

## 5. 启动前端 (1 分钟)

```bash
# Portal (Next.js, 19012)
cd community/portal
npm install
npm run dev  # 或 npm run build && npm start 跑生产

# App (Vue 3 SPA, 19013) — 需要 Python 跑 serve.py
cd ../app
SOHO_BACKEND=http://127.0.0.1:19011 python3 serve.py
```

## 6. 访问

| URL | 说明 |
|---|---|
| http://localhost:19011/docs | API 文档 (Swagger) |
| http://localhost:19012 | 获客门户 (匿名评估) |
| http://localhost:19013 | 服务平台 (admin/admin123 登录) |

---

## 验证一切正常

```bash
# 后端
curl http://localhost:19011/api/health
# {"ok":true,"service":"gobob-soho-core","db":"up","gobob_data_api":"..."}

# 登录拿 token
curl -X POST http://localhost:19011/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -m json.tool
```

---

## 故障排查

| 问题 | 解决 |
|---|---|
| `Connection refused` on 19011 | MySQL 没启, 或 `SOHO_MYSQL_HOST` 写错 |
| `ModuleNotFoundError: main` | 没装 requirements / 不在 venv |
| 评估 502 | 没设 `GOBOB_API_BASE` 或 API Key, 智能评估会失败 (但其他功能正常) |
| 端口被占 | `--port 19015` 换端口, 同步改 portal/app 的 backend URL |
