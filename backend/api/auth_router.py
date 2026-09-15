"""
api/auth_router.py — 登录 / 当前用户

学生 / 家长账号由机构在服务平台内创建（非公开注册），
获客门户的留资进 leads（不建账号）。这里只提供登录。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import auth
from core.database import db_cursor

router = APIRouter(prefix="/api", tags=["auth"])


class LoginReq(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.post("/login")
def login(req: LoginReq):
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, org_id FROM accounts WHERE username=%s LIMIT 1",
            (req.username,),
        )
        acc = cur.fetchone()
        if not acc or not auth.verify_password(req.password, acc["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        cur.execute(
            "SELECT id, role, name FROM members WHERE account_id=%s LIMIT 1",
            (acc["id"],),
        )
        mem = cur.fetchone()
    role = mem["role"] if mem else auth.ROLE_STUDENT
    token = auth.create_token(acc["id"], acc["username"], role, acc["org_id"])
    return {
        "token": token,
        "user": {
            "id": acc["id"],
            "username": acc["username"],
            "name": mem["name"] if mem else acc["username"],
            "role": role,
            "org_id": acc["org_id"],
            "member_id": mem["id"] if mem else None,
            "is_admin": role == auth.ROLE_OWNER,
        },
    }


@router.get("/me")
def me(user: dict = Depends(auth.get_current_user)):
    return {
        "id": user["sub"],
        "username": user["username"],
        "name": user.get("name"),
        "role": user["role"],
        "org_id": user["org_id"],
        "member_id": user.get("member_id"),
        "is_admin": user.get("is_admin"),
    }
