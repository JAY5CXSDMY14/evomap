#!/usr/bin/env bash
# 把 evoloop 模板装进目标仓库。已存在的文件不覆盖，生成 <file>.evoloop.new 供手动合并。
set -euo pipefail
TARGET="${1:?usage: install.sh /path/to/repo}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$TARGET/.git" ] || { echo "error: $TARGET is not a git repo" >&2; exit 1; }

copy() {  # copy <relative-src-under-templates-or-root> <relative-dst>
  local from="$1" to="$TARGET/$2"
  mkdir -p "$(dirname "$to")"
  if [ -e "$to" ]; then
    cp "$from" "$to.evoloop.new"; echo "  exists  $2  → wrote $2.evoloop.new"
  else
    cp "$from" "$to"; echo "  added   $2"
  fi
}

echo "Installing evoloop into $TARGET"
(cd "$SRC/templates" && find . -type f | sed 's|^\./||') | while read -r f; do
  copy "$SRC/templates/$f" "$f"
done
for d in prompts scripts; do
  (cd "$SRC/$d" && find . -type f | sed 's|^\./||') | while read -r f; do
    [ "$d/$f" = "scripts/install.sh" ] && continue
    copy "$SRC/$d/$f" "$d/$f"
  done
done
chmod +x "$TARGET"/scripts/*.sh 2>/dev/null || true

echo
echo "Next:"
echo "  1. 填写占位符:  grep -rn '{{' $TARGET/AGENTS.md $TARGET/docs/code-standards.md $TARGET/prompts"
echo "  2. 创建标签:    scripts/claim.sh --setup-labels"
echo "  3. 阅读:        evoloop/docs/adoption.md（分四期接入）"
