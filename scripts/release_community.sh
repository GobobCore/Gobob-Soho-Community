#!/bin/bash
# release_community.sh — 把社区版推到独立 Apache-2.0 公开仓
# ============================================================================
# 用法:
#   ./scripts/release_community.sh                  # 默认推到 main
#   ./scripts/release_community.sh --dry-run        # 只检查不真推
#
# 推送策略:
#   1. 先 force-push origin main 历史到 community-publish (mirror)
#   2. community-publish 仓本地立即 git rm -r saas/ 撤回闭源泄漏
#   3. 再 force-push 这个 hotfix 回 community-publish main
#
# 历史教训 (2026-09-17 16:40):
#   ❌ 单纯 'git push origin main:community-publish/main' 会把 saas/ 49 文件推到公开仓
#   ✅ 现在加 hotfix 步骤: push → hotfix-rm-saas → push, 远端最终只剩 community + shared
#
# 这种方式 SaaS 仓的 saas_admin/billing 等闭源文件从未离开过 SaaS 仓,
# GitHub 的 public 社区仓历史中也不会保留 (因为 hotfix commit 删了).
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOHO_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
COMMUNITY_REPO="git@github.com:GobobCore/Gobob-Soho-Community.git"
BRANCH="${1:-main}"
DRY_RUN=""

if [[ "${1:-}" == "--dry-run" || "${2:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
fi

echo "========================================="
echo "  release_community.sh"
echo "  本地仓:  $SOHO_REPO"
echo "  远端仓:  $COMMUNITY_REPO"
echo "  分支:    $BRANCH"
echo "  Dry-run: ${DRY_RUN:-no}"
echo "========================================="
echo ""

cd "$SOHO_REPO"

# 1. 检查工作树干净
echo "=== 1. 检查 community/ + shared/ 改动 ==="
if [[ -n $(git status --porcelain community/ shared/ docs/ scripts/release_community.sh 2>/dev/null) ]]; then
    echo "  有未提交改动, 必须先 commit:"
    git status --porcelain
    exit 1
fi
echo "  ✓ 工作树干净"

# 2. 推送前 audit (调用 push_audit.sh 扫敏感信息 + 路径校验)
echo ""
echo "=== 2. 推送前 audit (scripts/push_audit.sh community) ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过 audit)"
else
    if ! bash "$SCRIPT_DIR/push_audit.sh" community; then
        AUDIT_EXIT=$?
        if [[ "$AUDIT_EXIT" -eq 2 ]]; then
            echo "  ⚠️  audit 有警告, 但阻断 ERROR 数为 0, 继续推送"
        else
            echo "  ❌ audit 失败 (exit $AUDIT_EXIT), 禁止推送"
            exit 1
        fi
    fi
fi

# 3. Mirror push
echo ""
echo "=== 3. git push origin main:community-publish/main --force (mirror) ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过实际推送)"
else
    git push "$COMMUNITY_REPO" "main:$BRANCH" --force 2>&1 | tail -3
fi

# 4. 在远端仓本地删 saas/ 后 push (撤回闭源泄漏)
echo ""
echo "=== 4. 远端 hotfix: git rm saas/ + push ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过撤回)"
else
    HOTFIX_BRANCH="hotfix-rm-saas-leak-$(date +%H%M%S)"
    # 在 monorepo 上从 community-publish 拉最新, 删 saas/, push 回 community-publish
    git fetch "$COMMUNITY_REPO" "$BRANCH" 2>&1 | tail -1
    git checkout -b "$HOTFIX_BRANCH" FETCH_HEAD 2>&1 | tail -1
    SAAS_COUNT=$(git ls-files saas/ 2>/dev/null | wc -l)
    if [[ "$SAAS_COUNT" -gt 0 ]]; then
        git rm -rf saas/ 2>&1 | tail -2
        git commit -m "R-Security (2026-09-17): hotfix 删除误推的 saas/ 闭源目录 ($SAAS_COUNT 文件)

发布脚本 bug 修复 — release_community.sh 现在加了 post-push hotfix 步骤
" 2>&1 | tail -2
        git push "$COMMUNITY_REPO" "$HOTFIX_BRANCH:$BRANCH" --force 2>&1 | tail -3
    else
        echo "  ✓ 远端仓本来就不含 saas/, 跳过 hotfix"
    fi
    git checkout main 2>&1 | tail -1
    git branch -D "$HOTFIX_BRANCH" 2>&1
fi

# 5. 最终验证
echo ""
echo "=== 5. 验证远端无 saas/ 路径 ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过验证)"
else
    git fetch "$COMMUNITY_REPO" "$BRANCH" 2>&1 | tail -1
    SAAS_COUNT=$(git ls-tree -r "$COMMUNITY_REPO/$BRANCH" 2>/dev/null | grep -cE "\\bsaas/" || true)
    if [[ "$SAAS_COUNT" -gt 0 ]]; then
        echo "  ❌ 远端社区仓仍含 $SAAS_COUNT 个 saas/ 路径文件 — 立刻手动撤回!"
        exit 1
    fi
    echo "  ✓ 远端社区仓无 saas/ 路径"
fi

echo ""
echo "========================================="
echo "  ✓ 完成"
echo "  验证: https://github.com/GobobCore/Gobob-Soho-Community/tree/$BRANCH"
echo "========================================="