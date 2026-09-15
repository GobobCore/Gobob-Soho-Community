"""
core/config.py — Gobob SOHO 配置

从环境变量读取（docker-compose 注入 / 本地 .env）。
只保留 SOHO 需要的项；不含 Gobob 主仓的 SSO / 小程序 / 支付配置。
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── 数据库（SOHO 独立库）──
    db_host: str = os.environ.get("SOHO_MYSQL_HOST", "127.0.0.1")
    db_port: int = int(os.environ.get("SOHO_MYSQL_PORT", "3306"))
    db_user: str = os.environ.get("SOHO_MYSQL_USER", "soho")
    db_password: str = os.environ.get("SOHO_MYSQL_PASS", "")
    db_name: str = os.environ.get("SOHO_MYSQL_DB", "gobob_soho")

    # ── JWT ──
    jwt_secret: str = os.environ.get("SOHO_JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = int(os.environ.get("SOHO_JWT_EXPIRE_HOURS", "72"))

    # ── 初始管理员 / 机构（首次启动创建）──
    admin_username: str = os.environ.get("SOHO_ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("SOHO_ADMIN_PASSWORD", "")
    org_name: str = os.environ.get("SOHO_ORG_NAME", "我的留学工作室")

    # ── Gobob Data API（智能评估 / 院校数据，远程调用）──
    gobob_api_base: str = os.environ.get("GOBOB_API_BASE", "https://api.gobob.cn")
    gobob_api_key: str = os.environ.get("GOBOB_API_KEY", "")
    # 本地缓存 TTL（秒），避免每次评估都打远程
    gobob_cache_ttl: int = int(os.environ.get("GOBOB_CACHE_TTL", "86400"))  # 24h

    # ── 文件存储 ──
    storage_local_path: str = os.environ.get("SOHO_STORAGE_PATH", "./data/files")

    model_config = SettingsConfigDict(env_prefix="SOHO_")


def get_settings() -> Settings:
    # 不缓存：进程启动后 env 更新可感知（同 Gobob 主仓 2026-08-26 的教训）
    return Settings()
