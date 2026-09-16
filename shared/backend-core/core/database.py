"""
core/database.py — Gobob SOHO MySQL 连接

直连 PyMySQL（无 ORM），DictCursor。
"""

from contextlib import contextmanager

import pymysql

from .config import get_settings

settings = get_settings()


def get_db():
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


@contextmanager
def db_cursor():
    conn = get_db()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db_transaction():
    """事务上下文：关 autocommit，异常回滚。用于换师 / 签约等多步写。"""
    conn = get_db()
    conn.autocommit(False)
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit(True)
        conn.close()
