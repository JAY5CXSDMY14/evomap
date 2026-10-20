#!/bin/bash
# 把 build/Evo.app 打成 build/Evo.dmg（带「应用程序」快捷方式，拖进去即装）。
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-build}
VERSION=$(tr -d '[:space:]' < VERSION)
APP="$OUT/Evo.app"
[ -d "$APP" ] || { echo "先 make app"; exit 1; }
STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$OUT/Evo.dmg"
hdiutil create -volname "Evo $VERSION" -srcfolder "$STAGE" -ov -format UDZO -fs HFS+ "$OUT/Evo.dmg" >/dev/null
chmod -R u+w "$STAGE"; rm -rf "$STAGE"
du -h "$OUT/Evo.dmg" | awk '{print "Evo.dmg 大小 " $1}'
echo "$OUT/Evo.dmg"
