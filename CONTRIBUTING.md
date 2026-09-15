# Contributing to Gobob SOHO

感谢你的兴趣！

## 开发流程

1. Fork 本仓库，从 `main` 切功能分支
2. 提交前确保：
   - 后端 `pytest` 通过
   - 前端能 `build`
   - 不引入任何真实 API Key / 内部域名 / 私有数据
3. 提 PR，描述改动动机与影响面

## 代码约定

- 后端 FastAPI + 直连 MySQL（`core/database.py` 的 `db_cursor()`），不加 ORM
- ID 一律从 `core.id_gen` 导入（`new_id()` / `new_short_id()`），不 inline 调 uuid
- 所有业务表带 `org_id`，查询必须过租户隔离（`core/tenancy.py`）
- commit message：`<类型>: <一句话>`，类型如 `Feat / Fix / Refactor / Docs`

## 数据红线

院校 / 专业 / 匹配等数据**只能**通过 Gobob Data API 远程获取，严禁把数据快照或算法复制进本仓库。业务数据（线索 / 学生 / 合同）由使用者在自有数据库中管理。

## 报告问题

用 GitHub Issues，附复现步骤与环境（docker / 本地、浏览器、版本）。
