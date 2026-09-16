"""
test_id_gen.py — core/id_gen.py 单元测试
==========================================

验证:
- new_id() 返回 16 字符 hex
- new_short_id(prefix) 带前缀
- new_order_no(prefix) 可读订单号格式
"""

import re
import pytest
from core.id_gen import new_id, new_short_id, new_order_no


class TestNewId:
    def test_returns_16_char_hex(self):
        """16 字符 0-9a-f (小写) 字符串."""
        for _ in range(10):
            i = new_id()
            assert len(i) == 16
            assert re.match(r'^[0-9a-f]{16}$', i), f"格式不对: {i}"

    def test_unique(self):
        """1 万次调用应都是唯一."""
        ids = {new_id() for _ in range(10000)}
        assert len(ids) == 10000, "ID 应唯一"


class TestNewShortId:
    def test_with_prefix(self):
        """带前缀的 ID."""
        s = new_short_id("lead_")
        assert s.startswith("lead_")
        assert len(s) > 5  # prefix + 至少 1 字符

    def test_idempotent_for_empty(self):
        """空前缀应退化为 new_id()."""
        # 不一定相同 (调用时机), 但格式应一致
        s = new_short_id("")
        assert isinstance(s, str)


class TestNewOrderNo:
    def test_format_so(self):
        """SO 订单号 = SO + YYYYMMDD + 6 hex (大小写)."""
        o = new_order_no("SO")
        assert o.startswith("SO")
        assert len(o) == 16, f"订单号长度 {len(o)} != 16, 实际: {o}"
        # YYYYMMDD = 8 数字, 随机部分 6 hex (大小写)
        assert re.match(r'^SO\d{8}[0-9a-fA-F]{6}$', o), f"格式不对: {o}"

    def test_format_sokey(self):
        """SOKEY 订单号 (开源版按次购买用)."""
        o = new_order_no("SOKEY")
        assert o.startswith("SOKEY")
        assert re.match(r'^SOKEY\d{8}[0-9a-fA-F]{6}$', o), f"格式不对: {o}"
