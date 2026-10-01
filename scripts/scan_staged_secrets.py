#!/usr/bin/env python3
"""
scan_staged_secrets.py — 扫描暂存区新增行中的高置信凭据
=========================================================

只扫 `git diff --cached` 的**新增行**, 不扫历史 —— 否则旧提交里已存在的
内容会一直报, 钩子就没人愿意用了。

R-Security 2026-10-01: 2026-09-17 曾因 --force push 把含 saas/ 闭源码的
完整历史推入公开仓, 持续两周无人发现。本脚本是第一道本地拦截。

用法:
    python3 scripts/scan_staged_secrets.py            # 违规则 exit 1
    python3 scripts/scan_staged_secrets.py --quiet    # 只在有违规时输出

退出码: 0 = 干净, 1 = 发现高置信凭据
"""
import argparse
import re
import subprocess
import sys

# 高置信度模式 —— 只匹配几乎不可能出现在正常代码里的形态。
# 宁可漏报也不要误报: 一旦有误报, 钩子就会被 --no-verify 绕过, 等于没有。
PATTERNS = [
    ("GitHub token",      re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("GitHub fine-grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("私钥块",            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS AccessKey",     re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS SecretKey",     re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"][A-Za-z0-9/+=]{40}['\"]")),
    ("Slack token",       re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe secret",     re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b")),
    ("Google API key",    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("JWT",               re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("URL 内嵌口令",       re.compile(r"://[^/\s:@]+:[^/\s:@]{8,}@")),
]

# 这些行天然会命中（如示例、占位符、正则本身），跳过整行
SKIP_LINE_RX = re.compile(
    r"(?i)(example|sample|placeholder|dummy|fake|your[_-]?\w*|changeme|"
    r"xxxxx|\.\.\.|<[^>]+>|\$\{|\{\{|process\.env|os\.environ|getenv|"
    r"REDACTED|待法务|占位符)"
)


def staged_added_lines() -> list[tuple[str, int, str]]:
    """返回暂存区新增行 [(文件, 行号, 内容)]。"""
    out = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--no-color"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return []

    results = []
    current = None
    new_lineno = 0
    for line in out.stdout.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        if line.startswith("@@"):
            # @@ -a,b +c,d @@  → 新文件起始行 c
            m = re.search(r"\+(\d+)", line)
            new_lineno = int(m.group(1)) if m else 1
            continue
        if line.startswith("+") and not line.startswith("+++"):
            results.append((current, new_lineno, line[1:]))
            new_lineno += 1
        elif not line.startswith("-"):
            new_lineno += 1
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="只在有违规时输出")
    args = ap.parse_args()

    added = staged_added_lines()
    if not added:
        return 0

    findings = []
    for path, lineno, text in added:
        if not path or SKIP_LINE_RX.search(text):
            continue
        for name, rx in PATTERNS:
            for m in rx.finditer(text):
                # 只回报位置与模式名, 绝不回显命中值 —— 避免凭据经由终端/日志二次泄露
                findings.append((path, lineno, name))
                break

    if not findings:
        if not args.quiet:
            print(f"  ✓ 暂存区无高置信凭据 ({len(added)} 行新增)")
        return 0

    print("\n❌ 暂存区发现疑似凭据 —— 已阻断提交\n", file=sys.stderr)
    for path, lineno, name in findings:
        print(f"  {path}:{lineno}  [{name}]", file=sys.stderr)
    print(
        "\n若为误报（如示例/占位符）, 请在该行加注释说明, 例如:\n"
        '  # scan-staged-secrets: example key, safe\n'
        "确认是真凭据时, 请立即轮换该密钥, 勿仅从代码中删除。\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
