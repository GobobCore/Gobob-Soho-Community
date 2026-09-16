# Gobob SOHO 社区版 (Community Edition)

> **面向中小型留学机构与语言培训工作室的开源业务管理系统** (单机构自托管版本)
>
> 覆盖完整闭环：**获客(智能评估引流) → 线索/生源管理 → 签约 → 留学进程服务 → 老师协作与换师 → 老板管理视图**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-compose-blue)](deploy/docker-compose.yml)

---

## 这是什么

**Gobob SOHO 社区版** 是**单机构自托管版**, 专为 3-30 人的小型留学机构 / 工作室设计,
机构自己私有化部署, **所有数据 (线索/学生/合同) 存在自己数据库里**.

**跟 SaaS 版的区别**:
- 社区版 (本仓库): 单机构, 自托管, 免费, 自己买 Gobob Data API 调用次数 (¥1/次)
- SaaS 版: 多机构, 官方托管, 订阅制 (1-2 协作账号免费, ≥3 每账号 ¥1000/年),
  Gobob Data API 调用**包在服务费里不限次**

**跟 Gobob 主站的关系**:
SOHO 是独立运营项目, 跟 [Gobob 主站](https://github.com/GobobCore) 无业务交集.
SOHO 只调 Gobob Data API (院校/专业/排名/匹配算法), 业务核心 (线索/学生/合同) 完全独立.

---

## 功能

- **获客门户 (Next.js 14)**: 学生匿名做智能选校评估, 留资进线索池
- **CRM 生源管理**: 线索 → 跟进 → 转化 → 签约, 看板 + 漏斗 + 来源 ROI
- **签约与服务进程**: 合同, 收款登记, 按环节 (选校/考试/文书/面试/签证) 分配老师
- **换师机制**: 老师离职/调整, 交接任务 + 通知 (handover 模式)
- **管理驾驶舱**: 老板/主管一眼看学生进度
- **学生/家长端 (Vue 3 SPA)**: 自己的进度/任务/合同/消息

---

## 快速开始 (5 分钟)

### 1. 克隆 + 准备

```bash
git clone https://github.com/GobobCore/Gobob-SOHO.git
cd Gobob-SOHO
cp community/.env.example .env
# 编辑 .env 填密码 + (可选) Gobob API Key
```

### 2. 一键启动 (Docker)

```bash
cd community/deploy
cp ../.env.example .env
docker compose up -d
# 等 30 秒初始化
```

### 3. 访问

- 获客门户: http://localhost:19012
- 服务平台: http://localhost:19013
- API 文档: http://localhost:19011/docs
- 默认管理员: admin / (你 .env 里的 SOHO_ADMIN_PASSWORD)

### 4. (可选) 申请 Gobob Data API Key

智能评估需要 `gob_smb_...` 形式的 Key. 申请流程见 [GETTING_GOBOB_API_KEY.md](GETTING_GOBOB_API_KEY.md).
填到 .env 的 `GOBOB_API_KEY` 即可.

> 没有 Key 也能跑: 核心业务功能 (线索/签约/学生) 不依赖 Gobob, 仅"智能评估"和"院校数据"不可用.

---

## 仓库结构 (社区版)

```
Gobob-SOHO/                          # 本仓库 (Apache-2.0)
├── shared/                          # 业务核心 — 社区版和 SaaS 版共用
│   └── backend-core/                # FastAPI 业务路由 + core 模块
│       ├── api/                     # 14 个业务路由 (leads/contracts/students/...)
│       ├── core/                    # 6 个基础模块
│       ├── sql/                     # schema.sql + seed.sql + migrations/
│       └── main.py                  # FastAPI 工厂
├── community/                       # ← 本 README 的根
│   ├── backend/main.py              # 开源版入口 (85 业务路由, 无 SaaS)
│   ├── portal/                      # Next.js 14 获客门户
│   ├── app/                         # Vue 3 SPA 服务平台
│   ├── deploy/                      # docker-compose + Dockerfile × 3
│   ├── .env.example
│   ├── LICENSE                       # Apache-2.0
│   └── README.md                    # 本文件
└── cloud/                           # SaaS 闭源 (不在本仓, 单独仓库)

发布模式:
  社区版 (本仓库) → 推 GitHub 公开
  SaaS 闭源 → 单仓内部 Gitea (主仓 mirror 不带)
```

---

## 端口 (社区版默认)

| 端口 | 服务 | 说明 |
|---|---|---|
| **19011** | backend | FastAPI 业务 API |
| **19012** | portal | 获客门户 (Next.js) |
| **19013** | app | 服务平台 (Vue 3 SPA) |

> 选 1901x 避开 SaaS 版 1900x + Gobob 主站 188xx.

---

## 商业模式 (社区版)

- **软件**: Apache-2.0, 免费
- **Gobob Data API 调用**: 按次 ¥1, 在 https://www.gobob.cn 单独购买 Key

> 需要更复杂的订阅/计费/多机构管理? 用 [Gobob SOHO SaaS 版](联系 ops@gobob.cn).

---

## 文档

- [快速开始 (本机裸机)](QUICKSTART.md) - 不用 Docker, 直接 Python 跑
- [部署指南 (Docker)](deploy/docker-compose.yml) - 一键起栈
- [获取 Gobob API Key](GETTING_GOBOB_API_KEY.md)
- [贡献指南](CONTRIBUTING.md)
- [Apache-2.0 License](LICENSE)

---

## License

[Apache-2.0](LICENSE) © 2026 GobobCore

### Gobob Data API 引用说明

Gobob SOHO 社区版使用 [Gobob Data API](https://www.gobob.cn) 提供院校/专业/排名/智能匹配等数据能力.
使用 Gobob Data API 需遵守 Gobob 的数据使用条款.
你的业务数据 (线索/学生/合同) 100% 存储在你自己部署的数据库中, 不会上传到 Gobob.
