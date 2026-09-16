"""
core/tenancy.py — 多机构（多租户）数据隔离

所有业务表带 org_id。当前登录用户的 org_id 由 auth.get_current_user 注入。
本模块提供统一的 org 过滤，杜绝跨机构越权。

开源自托管默认单机构（orgs 表里 1 行）；同一套代码未来可支持 SaaS 多机构。
"""

from fastapi import Depends, HTTPException

from .auth import get_current_user


def get_org_id(user: dict = Depends(get_current_user)) -> str:
    """从当前用户解析 org_id，注入到查询。无 org_id 视为异常（数据隔离底线）。"""
    org_id = user.get("org_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="账号未关联机构")
    return org_id


def org_where(org_id: str, column: str = "org_id") -> tuple[str, list]:
    """生成 `AND org_id=%s` 片段与参数。配合 db_cursor 使用：

        where, params = org_where(org_id)
        cur.execute(f"SELECT * FROM leads WHERE 1=1 {where}", params)
    """
    return f" AND {column}=%s", [org_id]
