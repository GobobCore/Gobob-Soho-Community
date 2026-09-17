#!/bin/bash
# release_saas.sh — 把 SaaS 版 (saas/ + shared/) 推到 SaaS 独立私有仓
# ============================================================================
# 用法:
#   ./scripts/release_saas.sh                  # 默认推到 main
#   ./scripts/release_saas.sh --dry-run        # 只检查不真推
#
# 推送内容:
#   saas/backend/           (SaaS 后端 + saas_admin + billing)
#   saas/app/               (SaaS 平台前端 19003)
#   saas/soho-ops/          (SaaS 运营后台 19004)
#   saas/backend/scripts/   (aggregate_saas_usage.py 等)
#   shared/backend-core/    (业务核心)
#   shared/frontend-shared/ (共享前端, 当前空)
#
# 不推送:
#   community/              (开源版独立仓)
#   deploy/docker-compose.yml 含 community 镜像的 (推送前手动 review)
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

# 1. 检查 saas/ 改动
echo "=== 1. 检查 saas/ 改动 ==="
if [[ -n $(git status --porcelain saas/ shared/) ]]; then
    echo "  有未提交改动, 必须先 commit:"
    git status --porcelain saas/ shared/
    exit 1
fi
echo "  ✓ 工作树干净"

# 2. 敏感信息检查
echo ""
echo "=== 2. 敏感信息扫描 (API key / 客户名单 / 真实密码) ==="
SENSITIVE=$(grep -rE "MINIMAX_API_KEY|DEEPSEEK_API_KEY|GOBOB_MYSQL_PASS.*=" saas/backend/ saas/app/ saas/soho-ops/ 2>/dev/null | head -5 || true)
if [[ -n "$SENSITIVE" ]]; then
    echo "  ⚠️  发现疑似敏感信息:"
    echo "$SENSITIVE"
    echo "  请先脱敏再推送"
    exit 1
fi
echo "  ✓ 未发现明显敏感信息"

# 3. 推送 saas/ subtree
echo ""
echo "=== 3. git subtree push --prefix=saas ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过实际推送)"
else
    git subtree push --prefix=saas "$SAAS_REPO" "$BRANCH"
fi

# 4. 推送 shared/backend-core
echo ""
echo "=== 4. git subtree push --prefix=shared/backend-core ==="
if [[ -n "$DRY_RUN" ]]; then
    echo "  (dry-run, 跳过实际推送)"
else
    git subtree push --prefix=shared/backend-core "$SAAS_REPO" "$BRANCH-shared-core" --squash 2>&1 || \
        echo "  ⚠️  shared/backend-core 推送失败, 手动 git push 处理"
fi

echo ""
echo "========================================="
echo "  ✓ 完成"
echo "  验证: https://github.com/GobobCore/Gobob-Soho-SaaS/tree/$BRANCH"
echo "========================================="