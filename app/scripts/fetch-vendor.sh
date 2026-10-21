#!/bin/bash
# 第三方表情引擎（aora-bot，固定 commit）不进公开仓库：许可只许个人自用，不得再分发。
# 构建时从上游原仓库下载到 app/Resources/vendor/（已 .gitignore），并做唯一一处改动（睡眠 Z 字体换系统字体）。
# 许可与用法限制见 app/Resources/VENDOR-NOTICE.md。
set -euo pipefail
cd "$(dirname "$0")/.."
REV=e3b6148c818da4a8e1966f2bc89cdb3cee473b73
DST=Resources/vendor
if [ -f "$DST/.rev" ] && [ "$(cat "$DST/.rev")" = "$REV" ]; then exit 0; fi
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://codeload.github.com/sam70361/aora-bot/tar.gz/$REV" | tar xz -C "$TMP"
SRC="$TMP/aora-bot-$REV"
rm -rf "$DST"; mkdir -p "$DST/emotion-ball/js" "$DST/mood-mates/docs"
cp "$SRC"/LICENSE "$SRC"/LICENSE-COMMERCIAL.md "$SRC"/NOTICE.md "$DST/emotion-ball/"
cp "$SRC"/emotion-ball/js/{rings,emotions,ball,engine}.js "$DST/emotion-ball/js/"
cp "$SRC"/mood-mates/{LICENSE,LICENSE-COMMERCIAL.md,README.md} "$DST/mood-mates/"
cp "$SRC"/mood-mates/docs/{CHARACTER-DESIGN,DESIGN-PROVENANCE,INTEGRATION}.md "$DST/mood-mates/docs/"
cp -R "$SRC"/mood-mates/src "$DST/mood-mates/src"
for f in "$DST/emotion-ball/js/ball.js" "$DST/mood-mates/src/core/render.js"; do
  sed -i.bak "s/'Space Grotesk', 'Noto Sans SC'/-apple-system, 'PingFang SC'/g" "$f" && rm -f "$f.bak"
done
cp Resources/VENDOR-NOTICE.md "$DST/NOTICE.md"
echo "$REV" > "$DST/.rev"
