# API 概览

backend 提供 REST API，完整交互文档在运行后访问 `http://localhost:19001/docs`（Swagger）。

鉴权：`Authorization: Bearer <token>`（`POST /api/login` 获取）。所有业务数据按 `org_id` 机构隔离。

## 角色

`owner`（主管，全量）/ `advisor`（顾问，自己名下）/ `student` / `parent`

## 主要端点

### 认证
- `POST /api/login` 登录
- `GET /api/me` 当前用户

### 线索（CRM）
- `POST /api/leads` 录入（员工）
- `POST /api/leads/capture` 获客门户留资（匿名）
- `GET /api/leads` 列表 / `GET /api/leads/board` 看板
- `GET /api/leads/{id}` 详情（含跟进记录）
- `POST /api/leads/{id}/move-stage` 推进阶段
- `POST /api/leads/{id}/assign` 分配顾问（owner）
- `POST /api/leads/{id}/activities` 记跟进
- `POST /api/leads/{id}/convert` 转化为学生
- `GET /api/leads/stats/funnel` 漏斗

### 签约
- `GET /api/contracts/modules` 服务模块目录（13 个）
- `POST /api/contracts` 新建合同（选服务包）
- `GET /api/contracts` 列表（员工全量 / 学生看自己）
- `GET /api/contracts/{id}` 详情（含收款记录）
- `POST /api/contracts/{id}/payments` 收款登记

### 分配与换师
- `POST /api/assignments` 按环节分配老师（overall/exam/writing/school/interview/visa）
- `POST /api/assignments/{id}/handover` **换师**（交接说明必填，通知新旧老师+学生+家长+审计）
- `GET /api/assignments` 列表
- `POST /api/assignments/deliverables` 交付物

### 学生与进程
- `GET /api/students` 学生列表（老板全量/顾问看名下）
- `GET /api/students/{id}` 详情聚合（档案+负责老师+评估快照）
- `PUT /api/students/{id}/profile|academic|intent` 档案
- `POST/GET /api/workflow/applications|milestones|tasks` 进程
- `GET /api/workflow/notifications` 通知

### 模板
- `POST /api/templates` 建任务模板
- `POST /api/templates/{id}/instantiate` 实例化到学生（生成任务）

### 管理
- `GET /api/staff` 员工（owner）
- `POST /api/staff` 添加员工
- `GET /api/dashboard/overview` 驾驶舱聚合
- `GET /api/dashboard/students-progress` 学生进度总览

### 沟通
- `POST /api/messages` 发消息
- `GET /api/messages/conversations` 会话列表
- `GET /api/messages/with/{member_id}` 对话记录

### 评估（代理 Gobob）
- `GET /api/assessment/meta` 表单元数据
- `POST /api/assessment/match` 智能匹配（匿名，存快照）
- `GET /api/assessment/schools/lookup` 院校联想
- `GET /api/assessment/majors` 专业列表
- `POST /api/assessment/ai-ask` AI 问答
