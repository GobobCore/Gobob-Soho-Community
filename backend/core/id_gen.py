"""
core/id_gen.py — Gobob SOHO 统一 ID 生成

约定（与 Gobob 主仓一致）：
- 所有 entity ID:   new_id()            → 16 hex chars
- 带前缀短 ID:      new_short_id(pfx)   → f"{pfx}{hex[:12]}"
- 可读订单号:       new_order_no("CT")  → f"CT20260915A1B2C3"  (合同)

严禁 inline `import uuid` / 重复定义 new_id。
"""

import uuid as _uuid
from datetime import datetime


def new_id() -> str:
    """16 字符 hex ID（标准 entity ID）。"""
    return _uuid.uuid4().hex[:16]


def new_short_id(prefix: str, length: int = 12) -> str:
    """带前缀短 ID，如 new_short_id("lead_") → "lead_a1b2c3d4e5f6"。"""
    return f"{prefix}{_uuid.uuid4().hex[:length]}"


def new_order_no(prefix: str = "CT") -> str:
    """可读单号，如 new_order_no("CT") → "CT20260915A1B2C3"。

    CT = Contract（签约合同）。前缀 <YYYYMMDD><6 位 hex 大写>。
    """
    return f"{prefix}{datetime.now().strftime('%Y%m%d')}{_uuid.uuid4().hex[:6].upper()}"
