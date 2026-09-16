#!/bin/bash
# push_community_subtree.sh — 把 community/ 推到独立 repo
# ============================================================================
# 用法:  PM 在 GitHub 端建 GobobCore/Gobob-SOHO-Community 后, 跑这个脚本.
# 一次性: 30 秒内完成.
# 之后: 每次 community/ 改动, 跑
#        git subtree push --prefix=community git@github.com:GobobCore/Gobob-SOHO-Community.git main
# ============================================================================

set -e

SOHO_REPO=/home/ricky/.openclaw/workspace/gobob-soho
COMMUNITY_REPO="git@github.com:GobobCore/Gobob-SOHO-Community.git"

cd "$SOHO_REPO"

echo "=== 1. 准备: 检查当前分支 + community 目录 ==="
git rev-parse --abbrev-ref HEAD
ls community/ | head -10

echo ""
echo "=== 2. push community/ (独立历史) 到独立 repo ==="
git subtree push --prefix=community "$COMMUNITY_REPO" main

echo ""
echo "=== 3. 验证 ==="
echo "   https://github.com/GobobCore/Gobob-SOHO-Community 应有社区版代码"
echo "   包含: backend/  portal/  app/  deploy/  README.md  LICENSE  CONTRIBUTING.md  QUICKSTART.md"
echo "   (注: shared/ 不在 — 社区版需要的代码会被复制到 shared/ 目录)"
