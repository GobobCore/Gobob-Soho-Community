# 配置说明

所有配置走环境变量（`.env`）。模板见根目录 `.env.example`。

## 数据库

| 变量 | 默认 | 说明 |
|---|---|---|
| `SOHO_MYSQL_HOST` | `127.0.0.1`（docker 内 `mysql`）| 数据库主机 |
| `SOHO_MYSQL_PORT` | `3306` | 端口 |
| `SOHO_MYSQL_DB` | `gobob_soho` | 库名 |
| `SOHO_MYSQL_USER` | `soho` | 用户 |
| `SOHO_MYSQL_PASS` | — | 密码（必填）|
| `MYSQL_ROOT_PASSWORD` | — | docker 初始化 root 密码 |

## JWT

| 变量 | 默认 | 说明 |
|---|---|---|
| `SOHO_JWT_SECRET` | `change-me-in-production` | 签名密钥，**生产必改**，用 `openssl rand -hex 32` |
| `SOHO_JWT_EXPIRE_HOURS` | `72` | token 有效期 |

## 初始机构 / 管理员

| 变量 | 默认 | 说明 |
|---|---|---|
| `SOHO_ADMIN_USERNAME` | `admin` | 初始管理员用户名 |
| `SOHO_ADMIN_PASSWORD` | — | 初始管理员密码（设了才创建）|
| `SOHO_ORG_NAME` | `我的留学工作室` | 机构名 |

## Gobob Data API

| 变量 | 默认 | 说明 |
|---|---|---|
| `GOBOB_API_BASE` | `https://api.gobob.cn` | Gobob API 地址 |
| `GOBOB_API_KEY` | 空 | SMB Key（留空则智能评估关闭，核心业务不受影响）|
| `GOBOB_CACHE_TTL` | `86400` | Gobob 数据本地缓存秒数 |

## 端口

`SOHO_BACKEND_PORT=19001` / `SOHO_PORTAL_PORT=19002` / `SOHO_APP_PORT=19003`
