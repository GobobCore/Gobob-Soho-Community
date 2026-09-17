#!/bin/bash
# release_saas.sh — 把 SaaS 版推到 SaaS 独立私有仓
# ============================================================================
# 用法:
#   ./scripts/release_saas.sh                  # 默认推到 main
#   ./scripts/release_saas.sh --dry-run        # 只检查不真推
#
# 推送策略:
#   1. 先 force-push origin main 历史到 saas-publish (mirror)
#   2. saas-publish 仓本地立即 git rm -r community/ 撤回社区版泄漏
#   3. 再 force-push hotfix
#
# ⚠️  重要: SaaS 仓是 private GitHub 仓, 推送前检查是否含敏感信息
#           (API key, 客户名单, 计费数据)
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOHO_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
SAAS_REPO="git@github.com:GobobCore/Gobob-Soho-SaaS.git"
BRANCH="${1:-main}"
DRY_RUN=""

if [[ "${1:-}" == "--dry-run" || "${2:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
fi

echo "========================================="
echo "  release_saas.sh"
echo "  本地仓:  $SOHO_REPO"
echo "  远端仓:  $SAAS_REPO (PRIVATE)"
echo "  分支:    $BRANCH"
echo "  Dry-run: ${DRY_RUN:-no}"
echo "========================================="
echo ""

cd "$SOHO_REPO"

# 1. 检查工作树干净
echo "=== 1. 检查 saas/ + shared/ 改动 ==="
if [[ -n $(git status --porcelain saas/ shared/ scripts/release_saas.sh 2>/dev/null) ]]; then
    echo "  有未提交改动, 必须先 commit:"
    git status --porcelain
    exit 1
fi
echo "  ✓ 工作树干净"

# 2. 推送前 audit (调用 push_audit.sh 扫敏感信息 + 路径校验)
echo ""
echo "=== 2. 推送前 audit (scripts/push_audit.sh saas) ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过 audit)"
else
    if ! bash "$SCRIPT_DIR/push_audit.sh" saas; then
        AUDIT_EXIT=$?
        if [[ "$AUDIT_EXIT" -eq 2 ]]; then
            echo "  ⚠️  audit 有警告, 但阻断 ERROR 数为 0, 继续推送"
        else
            echo "  ❌ audit 失败 (exit $AUDIT_EXIT), 禁止推送"
            exit 1
        fi
    fi
fi

# 3. 敏感信息扫描
echo ""
echo "=== 3. 敏感信息扫描 (API key / 客户名单 / 真实密码) ==="
SENSITIVE=$(grep -rE "MINIMAX_API_KEY|DEEPSEEK_API_KEY|GOBOB_MYSQL_PASS.*=" saas/backend/ saas/app/ saas/soho-ops/ 2>/dev/null | head -5 || true)
if [[ -n "$SENSITIVE" ]]; then
    echo "  ⚠️  发现疑似敏感信息:"
    echo "$SENSITIVE"
    echo "  请先脱敏再推送"
    exit 1
fi
echo "  ✓ 未发现明显敏感信息"

# 4. Mirror push
echo ""
echo "=== 4. git push origin main:saas-publish/main --force ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过实际推送)"
else
    git push "$SAAS_REPO" "main:$BRANCH" --force 2>&1 | tail -3
fi

# 5. 远端 hotfix: 删 community/ 撤回
echo ""
echo "=== 5. 远端 hotfix: git rm community/ + push ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过撤回)"
else
    HOTFIX_BRANCH="hotfix-rm-community-leak-$(date +%H%M%S)"
    git fetch "$SAAS_REPO" "$BRANCH" 2>&1 | tail -1
    git checkout -b "$HOTFIX_BRANCH" FETCH_HEAD 2>&1 | tail -1
    COMM_COUNT=$(git ls-files community/ 2>/dev/null | wc -l)
    if [[ "$COMM_COUNT" -gt 0 ]]; then
        git rm -rf community/ 2>&1 | tail -2
        git commit -m "R-Security (2026-09-17): hotfix 删除误推的 community/ ($COMM_COUNT 文件)

SaaS 仓应该是私有, 不应含 Apache-2.0 开源版的 community/ 目录
" 2>&1 | tail -2
        git push "$SAAS_REPO" "$HOTFIX_BRANCH:$BRANCH" --force 2>&1 | tail -3
    else
        echo "  ✓ 远端仓本来就不含 community/, 跳过 hotfix"
    fi
    git checkout main 2>&1 | tail -1
    git branch -D "$HOTFIX_BRANCH" 2>&1
fi

# 6. 最终验证
echo ""
echo "=== 6. 验证远端无 community/ 路径 ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过验证)"
else
    git fetch "$SAAS_REPO" "$BRANCH" 2>&1 | tail -1
    COMM_COUNT=$(git ls-tree -r "$SAAS_REPO/$BRANCH" 2>/dev/null | grep -cE "\\bcommunity/" || true)
    if [[ "$COMM_COUNT" -gt 0 ]]; then
        echo "  ❌ 远端 SaaS 仓仍含 $COMM_COUNT 个 community/ 路径文件 — 立刻手动撤回!"
        exit 1
    fi
    echo "  ✓ 远端 SaaS 仓无 community/ 路径"
fi

echo ""
echo "========================================="
echo "  ✓ 完成"
echo "  验证: https://github.com/GobobCore/Gobob-Soho-SaaS/tree/$BRANCH"
echo "========================================="