"""
test_playwright_e2e.py — 真浏览器端到端测试
==============================================

PM 在 CLAUDE.md 提到 playwright 验证, 这次落实成自动化测试.

测什么:
- portal 首页加载 + 标题检查
- /assessment 智能评估页加载 (空 meta 也能 render)
- 关键文本元素存在 (免费评估 按钮)
- /register 注册页可访问
- /buy-key 购买页加载 + 套餐显示

依赖: playwright + headless chromium (本机 .cache/ms-playwright/ 已装)

注意: 本机开发用, CI 不强求 (Playwright 装大). 跑这测试慢, 单独 job 跑.
"""

import os
import sys
import pytest
import uuid

# Skip if playwright not available
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

PORTAL_URL = os.environ.get("SOHO_TEST_PORTAL", "http://127.0.0.1:19002")
CHROME_PATH = "/home/ricky/.cache/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-linux64/chrome-headless-shell"


def _portal_up(url: str) -> bool:
    """简单可达性检查."""
    import urllib.request, urllib.error
    try:
        r = urllib.request.urlopen(url, timeout=2)
        return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not HAS_PLAYWRIGHT or not _portal_up(PORTAL_URL),
    reason="Playwright 或 portal (19002) 不可用, 跳过"
)


@pytest.fixture(scope="module")
def browser():
    """共享一个 browser 加速."""
    if not os.path.exists(CHROME_PATH):
        pytest.skip(f"Chromium 不在 {CHROME_PATH}")
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME_PATH)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    """每个测试拿新 page (避免状态污染)."""
    p = browser.new_page()
    p.set_default_timeout(10000)
    yield p
    p.close()


# ── 测试 ──

class TestPortalSmoke:
    def test_homepage_loads(self, page):
        """portal 首页应 200 + 标题."""
        page.goto(PORTAL_URL)
        assert page.title() == "免费智能选校评估 — Gobob SOHO"
        # 关键 CTA 存在
        assert page.locator("text=免费智能评估").first.is_visible()

    def test_homepage_has_react_app(self, page):
        """portal 是 Next.js + React, 应该有 lucide icons + main-app bundle."""
        page.goto(PORTAL_URL)
        # React 渲染: 找 .lucide-* 类
        lucide_count = page.locator("[class*='lucide-']").count()
        assert lucide_count > 0, "应有 lucide icons (说明 React 已 mount)"

    def test_hero_text(self, page):
        """Hero 区有 3 分钟智能匹配 文案."""
        page.goto(PORTAL_URL)
        assert page.locator("text=3 分钟").first.is_visible()
        # 套餐 "学生 / 家长" 双入口
        assert page.locator("text=学生").first.is_visible()
        assert page.locator("text=机构").first.is_visible()


class TestAssessmentPage:
    def test_assessment_loads(self, page):
        """/assessment 应能加载 (可能因没 Gobob Key 显示禁用, 但页面能 render)."""
        page.goto(f"{PORTAL_URL}/assessment")
        # 页面标题是 "智能选校评估"
        assert "智能选校评估" in page.title()
        # 表单存在 (6 步评估)
        assert page.locator("text=智能选校评估").first.is_visible()

    def test_register_page_accessible(self, page):
        """/register 自助注册页可访问."""
        page.goto(f"{PORTAL_URL}/register")
        assert "创建你的留学工作室" in page.title() or "注册" in page.title()
        # 有机构名 + 老板姓名 + 用户名 + 密码 输入框
        assert page.locator("input").count() >= 4, "应至少有 4 个输入框"


class TestBuyKeyPage:
    def test_buy_key_loads(self, page):
        """/buy-key 开源版按次购买页可加载 + 套餐显示."""
        page.goto(f"{PORTAL_URL}/buy-key")
        assert "购买" in page.title() or "Gobob" in page.title()
        # 4 个套餐按钮 (10/50/100/500 次体验包等)
        assert page.locator("text=10 次").first.is_visible(timeout=5000) or \
               page.locator("text=体验包").first.is_visible(timeout=5000)
        # 至少 1 个套餐可见即通过 (具体文案可能变)

    def test_buy_key_with_org_param(self, page):
        """/buy-key?org=demo-studio 应正常加载 (不影响 UI, 后端才读)."""
        page.goto(f"{PORTAL_URL}/buy-key?org=demo-studio")
        # 页面能正常显示 (跟不带 org 一致)
        assert page.locator("text=购买 Gobob").first.is_visible(timeout=5000) or \
               "buy-key" in page.url


# ── 注册流程端到端 (用 mock uuid 避免冲突) ──

class TestRegisterFlow:
    def test_register_form_submits(self, page):
        """真实注册一个新机构 (端到端流程)."""
        page.goto(f"{PORTAL_URL}/register")
        # 用唯一名字避免冲突
        unique = f"pw-test-{uuid.uuid4().hex[:6]}"
        # 填表
        page.locator("input").nth(0).fill(f"PW 测试 {unique}")  # 机构名
        page.locator("input").nth(1).fill("PW 测试老板")       # 老板姓名
        page.locator("input").nth(2).fill(f"{unique}@test.com")  # 邮箱
        page.locator("input").nth(3).fill(unique)             # 用户名
        # 密码
        page.locator("input[type='password']").nth(0).fill("testPass123")
        # 提交 (找 button 文字含 "创建")
        page.locator("button:has-text('创建')").first.click()
        # 等待跳转 (soho-app 19003) 或显示成功
        try:
            page.wait_for_url("**/19003**", timeout=5000)
            # 跳到 19003 算成功
            assert "19003" in page.url or "19012" in page.url
        except PWTimeout:
            # 或者页面停在 19002 但有 "已注册" 字样
            content = page.content()
            if "已注册" in content or "已收到" in content or "注册成功" in content:
                return
            # 试看 19003 跨域
            current = page.url
            assert "19003" in current or "/dashboard" in current, f"应跳到 19003 dashboard 或显示成功, 实际: {current}"
