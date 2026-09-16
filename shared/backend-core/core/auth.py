"""
core/auth.py — Gobob SOHO JWT 认证

4 角色模型：owner（老板/主管）/ advisor（顾问·老师）/ student / parent。
无 SSO、无小程序 —— 纯 Bearer token。

members.role 存角色；accounts.is_admin 仅保留兼容（owner 即管理员）。
"""

from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, Header, HTTPException
from jose import jwt

from .config import get_settings
from .database import db_cursor

settings = get_settings()
# 直接用 bcrypt 库（passlib 1.7.4 与 bcrypt 4.x+ 不兼容，会导致 hash 失败）

# SOHO 四种角色
ROLE_OWNER = "owner"      # 老板/主管：全量
ROLE_ADVISOR = "advisor"  # 顾问/老师：自己的线索+学生
ROLE_STUDENT = "student"
ROLE_PARENT = "parent"
ALL_ROLES = {ROLE_OWNER, ROLE_ADVISOR, ROLE_STUDENT, ROLE_PARENT}
# 机构内部员工（可看机构端）
STAFF_ROLES = {ROLE_OWNER, ROLE_ADVISOR}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, username: str, role: str, org_id: str, **extra) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "org_id": org_id,
        "exp": expire,
        **extra,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.JWTError:
        return None


def get_current_user(authorization: str = Header(None)) -> dict:
    """严格鉴权：失败 401。返回含 sub/username/role/org_id/member_id/is_admin。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权（请用 Bearer token 登录）")
    payload = decode_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    # 每次从 DB 取最新角色 / org（不信任 JWT 缓存）
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.username, a.org_id,
                   m.id AS member_id, m.name, m.role
            FROM accounts a
            LEFT JOIN members m ON m.account_id = a.id
            WHERE a.id = %s
            LIMIT 1
            """,
            (payload.get("sub"),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="用户不存在或会话已失效，请重新登录")
    out = dict(payload)
    out["username"] = row.get("username") or payload.get("username")
    out["member_id"] = row.get("member_id")
    out["name"] = row.get("name")
    out["org_id"] = row.get("org_id") or payload.get("org_id")
    out["role"] = row.get("role") or payload.get("role")
    out["is_admin"] = out["role"] == ROLE_OWNER  # owner 即管理员
    return out


def get_optional_user(authorization: str = Header(None)) -> dict:
    """可选鉴权：游客返回 {"member_id": None, "is_guest": True}（获客门户用）。"""
    if not authorization or not authorization.startswith("Bearer "):
        return {"member_id": None, "is_guest": True, "sub": None}
    try:
        return get_current_user(authorization)
    except HTTPException:
        return {"member_id": None, "is_guest": True, "sub": None}


def require_owner(user: dict = Depends(get_current_user)) -> dict:
    """仅老板/主管（owner）。用于员工管理、全量数据、设置。"""
    if user.get("role") != ROLE_OWNER:
        raise HTTPException(status_code=403, detail="需要主管权限")
    return user


def require_staff(user: dict = Depends(get_current_user)) -> dict:
    """机构内部员工（owner / advisor）。学生/家长拒绝。"""
    if user.get("role") not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="需要机构员工权限")
    return user
