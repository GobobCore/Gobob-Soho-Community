#!/bin/bash
# install_git_hooks.sh — 把 scripts/git-hooks/ 装进 .git/hooks/
# =============================================================================
# .git/hooks/ 不受版本控制, 所以钩子本体放在 scripts/git-hooks/ 随仓分发,
# 由本脚本安装。新克隆仓库或 CI 容器里跑一次即可。
#
# 用法: ./scripts/install_git_hooks.sh
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/scripts/git-hooks"
DEST_DIR="$REPO_ROOT/.git/hooks"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "✗ 不是 git 仓库根目录"
  exit 1
fi

if [[ ! -d "$SRC_DIR" ]]; then
  echo "✗ 找不到 $SRC_DIR"
  exit 1
fi

mkdir -p "$DEST_DIR"
INSTALLED=0
for hook in "$SRC_DIR"/*; do
  [[ -f "$hook" ]] || continue
  name=$(basename "$hook")
  # 不覆盖 .sample 等模板, 也不覆盖已有的自定义钩子(除非同名就是我们的)
  if [[ -f "$DEST_DIR/$name" && ! -f "$DEST_DIR/$name.sample" ]]; then
    if ! grep -q "pre-commit\|本地快速门禁" "$DEST_DIR/$name" 2>/dev/null; then
      echo "⚠️  $DEST_DIR/$name 已存在且非本项目安装, 跳过"
      continue
    fi
  fi
  cp "$hook" "$DEST_DIR/$name"
  chmod +x "$DEST_DIR/$name"
  echo "  ✓ 已安装 $name"
  INSTALLED=$((INSTALLED + 1))
done

if [[ "$INSTALLED" -eq 0 ]]; then
  echo "没有可安装的钩子"
else
  echo ""
  echo "本地门禁已启用:"
  echo "  - 暂存区高置信凭据扫描"
  echo "  - shared 层架构边界 (仅在改动 shared/ 时运行, 约 1.4s)"
  echo ""
  echo "紧急绕过: git commit --no-verify"
  echo "全量测试请交给 CI; 本地跑: .venv/bin/python -m pytest shared/backend-core/tests/"
fi
