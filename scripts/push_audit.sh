#!/bin/bash
# push_audit.sh — release 推送前后的安全审计
# ============================================================================
# 用法:
#   ./scripts/push_audit.sh community           # 检查 monorepo + 远端社区仓
#   ./scripts/push_audit.sh saas                # 检查 monorepo + 远端 SaaS 仓
#   ./scripts/push_audit.sh community --skip-fetch  # 跳过远端 fetch 阶段 (本地快速检查)
#
# 检查项:
#   1. 敏感信息扫描 — API key, 密码, 内部 IP, 真实邮箱
#   2. 路径隔离 — monorepo 内 saas/ vs community/ 不混入
#   3. 远端路径隔离 — 推送后远端仓不能含不该有的路径
#
# 退出码:
#   0 = 通过
#   1 = 审计失败 (有 ERROR 级问题)
#   2 = 警告 (有 WARN 级问题, 但未阻断)
# ============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOHO_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET="${1:-}"
SKIP_FETCH=""

if [[ "${2:-}" == "--skip-fetch" || "${1:-}" == "--skip-fetch" ]]; then
    SKIP_FETCH="--skip-fetch"
fi

if [[ -z "$TARGET" || "$TARGET" != "community" && "$TARGET" != "saas" ]]; then
    echo "用法: $0 [community|saas] [--skip-fetch]"
    exit 1
fi

if [[ "$TARGET" == "community" ]]; then
    REMOTE_REPO="git@github.com:GobobCore/Gobob-Soho-Community.git"
    EXCLUDED_PATTERN="saas/"        # 社区仓禁止含 saas/
    EXCLUDED_LABEL="SaaS 闭源目录"
    MAIN_PATTERN="community/"        # 社区仓必须含 community/
elif [[ "$TARGET" == "saas" ]]; then
    REMOTE_REPO="git@github.com:GobobCore/Gobob-Soho-SaaS.git"
    EXCLUDED_PATTERN="community/"   # SaaS 仓禁止含 community/
    EXCLUDED_LABEL="社区版开源目录"
    MAIN_PATTERN="saas/"             # SaaS 仓主路径 (mirror monorepo, 顶层有 saas/ 目录)
fi

cd "$SOHO_REPO"

ERRORS=0
WARNS=0

# Helper: 输出问题
error() {
    echo "  ❌ ERROR: $1"
    ERRORS=$((ERRORS+1))
}
warn() {
    echo "  ⚠️  WARN: $1"
    WARNS=$((WARNS+1))
}
ok() {
    echo "  ✓ $1"
}

echo "========================================="
echo "  push_audit.sh"
echo "  Target: $TARGET (远端仓: $REMOTE_REPO)"
echo "  禁止路径: $EXCLUDED_PATTERN ($EXCLUDED_LABEL)"
echo "========================================="
echo ""

# 1. 敏感信息扫描
echo "=== 1. 敏感信息扫描 ==="
# SaaS 闭源目录 / 社区版代码
if [[ "$TARGET" == "community" ]]; then
    SCAN_DIRS="community/ shared/"
else
    SCAN_DIRS="saas/ shared/"
fi

# 敏感 key/密码/真实 IP 模式
# 注: 排除 node_modules/ .next/ .git/ dist/ build/ 等 build artifacts
SENSITIVE=$(grep -rEn \
    --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=.git \
    --exclude-dir=dist --exclude-dir=build --exclude-dir=__pycache__ \
    --exclude="*.svg" --exclude="*.png" --exclude="*.jpg" --exclude="*.gif" \
    --exclude="package-lock.json" --exclude="*.lock" --exclude="*.min.js" \
    -e "MINIMAX_API_KEY\s*=\s*['\"][a-zA-Z0-9]{20,}" \
    -e "DEEPSEEK_API_KEY\s*=\s*['\"][a-zA-Z0-9]{20,}" \
    -e "GOBOB_MYSQL_PASS\s*=\s*['\"][^'\"]{6,}" \
    -e "SOHO_MYSQL_PASS\s*=\s*['\"][^'\"]{6,}" \
    -e "GOBOB_API_KEY\s*=\s*['\"]gob_[a-zA-Z0-9_]{20,}" \
    -e "@192\.168\.[0-9]+\.[0-9]+" \
    -e "[a-zA-Z0-9._%+-]+@(gmail|163|qq|outlook|hotmail|yahoo)\.com" \
    $SCAN_DIRS 2>/dev/null | head -20 || true)

if [[ -n "$SENSITIVE" ]]; then
    error "发现疑似敏感信息 (共 $(echo "$SENSITIVE" | wc -l) 行):"
    echo "$SENSITIVE" | head -10
    echo "  请先脱敏再推送"
else
    ok "未发现 API key / 密码 / 内部 IP / 真实邮箱"
fi
echo ""

# 2. monorepo 内路径隔离检查
echo "=== 2. monorepo 内路径隔离检查 ==="
if [[ "$TARGET" == "community" ]]; then
    # 检查 monorepo 内 saas/ 在 git index 里
    SAAS_FILES=$(git ls-files saas/ 2>/dev/null | wc -l)
    echo "  monorepo 内有 $SAAS_FILES 个 saas/ 文件 (设计如此, hotfix 会撤回)"
    if [[ "$SAAS_FILES" -eq 0 ]]; then
        warn "monorepo 没有 saas/ 目录 (不符合 SaaS/社区 monorepo 设计)"
    fi
    ok "monorepo 设计正确 (saas/ 在 index, hotfix 会撤回)"
else
    # 检查 monorepo 内 community/ 在 git index 里
    COMM_FILES=$(git ls-files community/ 2>/dev/null | wc -l)
    echo "  monorepo 内有 $COMM_FILES 个 community/ 文件 (设计如此, hotfix 会撤回)"
    if [[ "$COMM_FILES" -eq 0 ]]; then
        warn "monorepo 没有 community/ 目录 (不符合 SaaS/社区 monorepo 设计)"
    fi
    ok "monorepo 设计正确 (community/ 在 index, hotfix 会撤回)"
fi
echo ""

# 3. 远端路径隔离检查 (可选, --skip-fetch 跳过)
echo "=== 3. 远端仓路径隔离检查 ==="
if [[ -n "$SKIP_FETCH" ]]; then
    echo "  (--skip-fetch, 跳过远端检查)"
else
    echo "  拉取远端 main HEAD..."
    # 每个 target 用独立 remote alias, 避免 FETCH_HEAD 引用混淆
    REMOTE_ALIAS="audit-${TARGET}"
    git remote add "$REMOTE_ALIAS" "$REMOTE_REPO" 2>/dev/null || git remote set-url "$REMOTE_ALIAS" "$REMOTE_REPO"
    git fetch "$REMOTE_ALIAS" main 2>&1 | tail -1

    # 远端不能含 EXCLUDED_PATTERN
    REMOTE_EXCLUDED=$(git ls-tree -r "$REMOTE_ALIAS/main" 2>/dev/null | grep -cE "[^/]${EXCLUDED_PATTERN}" || true)
    if [[ "$REMOTE_EXCLUDED" -gt 0 ]]; then
        error "远端 $TARGET 仓仍含 $REMOTE_EXCLUDED 个 ${EXCLUDED_PATTERN} 路径文件 — 必须先 hotfix 撤回!"
    else
        ok "远端 $TARGET 仓无 ${EXCLUDED_PATTERN} 路径"
    fi

    # 远端必须含主路径 (community 或 saas)
    REMOTE_MAIN=$(git ls-tree -r "$REMOTE_ALIAS/main" 2>/dev/null | grep -cE "[^/]${MAIN_PATTERN}" || true)
    if [[ "$REMOTE_MAIN" -eq 0 ]]; then
        error "远端 $TARGET 仓不含 ${MAIN_PATTERN} 路径 — mirror push 可能失败"
    else
        ok "远端 $TARGET 仓含 $REMOTE_MAIN 个 ${MAIN_PATTERN} 路径文件"
    fi

    # 清理临时 remote
    git remote remove "$REMOTE_ALIAS" 2>/dev/null
fi
echo ""

# 总结
echo "========================================="
echo "  总结: $ERRORS ERROR, $WARNS WARN"
if [[ "$ERRORS" -gt 0 ]]; then
    echo "  ❌ 审计失败, 禁止推送"
    exit 1
elif [[ "$WARNS" -gt 0 ]]; then
    echo "  ⚠️  有警告, 可继续 (但建议人工 review)"
    exit 2
else
    echo "  ✓ 通过, 可以推送"
    exit 0
fi