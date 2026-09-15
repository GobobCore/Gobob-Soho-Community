# Gobob SOHO

> 面向中小型留学机构与语言培训工作室的**开源业务管理系统**。
> 覆盖完整闭环：**获客（智能评估引流）→ 线索/生源管理 → 签约 → 留学进程服务 → 老师协作与换师 → 老板管理视图**。

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## 这是什么

Gobob SOHO 是一个**独立部署、独立数据库**的业务管理系统，专为 3–30 人的小型留学机构 / 工作室设计：

- **获客门户**：学生匿名做智能选校评估，留资后自动进入机构线索池
- **CRM 生源管理**：线索 → 跟进 → 转化 → 签约，看板 + 漏斗 + 来源 ROI
- **签约与服务进程**：合同、收款登记、按环节（选校/考试/文书/面试/签证…）分配老师、**灵活换师 + 交接**
- **管理驾驶舱**：老板/主管一眼看到所有学生的进度、谁负责、已完成/在做/待做
- **学生/家长端**：查看自己的进度、任务、文档、合同，与老师沟通

它与 [Gobob](https://github.com/GobobCore) 主平台**代码独立、部署独立**，仅通过 **Gobob Data API（API Key 授权）** 远程调用院校 / 专业 / 排名 / 智能匹配等数据能力 —— 你的业务数据（线索、学生、合同）完全在自己的数据库里。

---

## 架构

```
┌─────────────────────────── Gobob SOHO ───────────────────────────┐
│                                                                    │
│  portal/  获客门户 (Next.js)      app/  服务平台 (Vue3 SPA)         │
│  :19002   智能评估引流            :19003  机构端 + 学生/家长端       │
│       └──────────────┬────────────────┘                          │
│                      ▼                                            │
│              backend/  FastAPI + MySQL  :19001                    │
│                      │  gobob-data-client (缓存 + 熔断)            │
└──────────────────────┼─────────────────────────────────────────────┘
                       ▼  HTTPS + X-API-Key
              Gobob Data API  (/api/smb/v1/*)   ← 院校/专业/匹配 数据
```

---

## 快速开始

```bash
cp .env.example .env       # 填入你的配置（含 Gobob API Key，见下）
docker compose up -d       # 起 mysql + backend + portal + app
```

打开：
- 获客门户 http://localhost:19002
- 服务平台 http://localhost:19003 （默认管理员见 `.env.example` 说明）
- API 文档 http://localhost:19001/docs

### 获取 Gobob API Key

智能评估 / 院校库等数据能力由 Gobob Data API 提供。部署前你需要一个 `gob_smb_...` 形式的 API Key（免费申请，含调用配额）。申请流程见 [`docs/GETTING_GOBOB_API_KEY.md`](docs/GETTING_GOBOB_API_KEY.md)。

> 没有 Key 也能跑：线索 / 签约 / 进程 / 员工管理等核心业务功能不依赖 Gobob，仅"智能评估"和"院校数据"不可用。

---

## 仓库结构

```
backend/    FastAPI 业务 API（纯后端）
portal/     获客门户（Next.js 14，智能评估引流）
app/        服务平台（Vue 3 SPA，机构端 + 学生/家长端）
docs/       文档（部署 / 配置 / API / 贡献）
deploy/     docker-compose 与部署脚本
```

---

## 文档

- [部署指南](docs/DEPLOY.md)
- [配置说明](docs/CONFIG.md)
- [API 说明](docs/API.md)
- [贡献指南](CONTRIBUTING.md)

---

## License

[Apache-2.0](LICENSE) © 2026 GobobCore

Gobob SOHO 是开源项目。院校 / 专业 / 匹配等数据能力由 Gobob Data API 提供，需遵守其数据使用条款。你的业务数据（线索、学生、合同）100% 存储在你自己部署的数据库中。
