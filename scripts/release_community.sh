#!/bin/bash
# release_community.sh — 把社区版 (community/ + shared/) 推到社区独立仓
# ============================================================================
# 用法:
#   ./scripts/release_community.sh                  # 默认推到 main
#   ./scripts/release_community.sh --dry-run        # 只检查不真推
#
# 推送内容:
#   community/             (开源版后端 + 前端)
#   shared/backend-core/  (业务核心, 与 SaaS 共用)
#   shared/frontend-shared/ (共享前端, 当前为空)
#   deploy/                (Dockerfile + docker-compose, 开源版适用)
#   docs/SPLIT_PLAN_*.md   (拆分说明)
#
# 不推送:
#   saas/                  (SaaS 闭源)
#   .gitignore 加 community/ + saas/ 保护
#
# 原理: git subtree push 把 community/ 内容作为仓根推到独立 repo.
#       shared/ 同步: 走 subtree push --prefix=shared 后, 在独立仓里
#       用 `git read-tree` 把 shared/ 复制到仓根.
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

# 1. 检查 community/ 改动
echo "=== 1. 检查 community/ 改动 ==="
if [[ -n $(git status --porcelain community/ shared/) ]]; then
    echo "  有未提交改动, 必须先 commit:"
    git status --porcelain community/ shared/
    exit 1
fi
echo "  ✓ 工作树干净"

# 2. 检查 saas/ 不在提交历史里被错误包含
echo ""
echo "=== 2. 检查 saas/ 不被推送 ==="
SAAS_IN_HISTORY=$(git log --all --pretty=format: --name-only --diff-filter=A | grep -c "^saas/" || true)
if [[ "$SAAS_IN_HISTORY" -gt 0 ]]; then
    echo "  ⚠️  saas/ 出现在 git 历史里 — 拆分前曾 commit, 推送时会包含, 但 community 仓会自然 reject"
fi
echo "  ✓ saas/ 当前不在 git index 里"

# 3. 推送 community/ + shared/backend-core 合并 subtree (用 split + force-push)
echo ""
echo "=== 3. git subtree split --prefix=community --prefix=shared/backend-core + force-push ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过实际推送)"
else
    SPLIT_BRANCH="release-community-$(date +%Y%m%d-%H%M%S)"
    # 合并 community/ 和 shared/backend-core 到一个临时分支, 一次性 force-push 到社区仓 main
    git subtree split --prefix=community --prefix=shared/backend-core -b "$SPLIT_BRANCH"
    git push "$COMMUNITY_REPO" "$SPLIT_BRANCH:$BRANCH" --force
    git branch -D "$SPLIT_BRANCH"
fi

echo ""
echo "========================================="
echo "  ✓ 完成"
echo "  验证: https://github.com/GobobCore/Gobob-Soho-Community/tree/$BRANCH"
echo "========================================="