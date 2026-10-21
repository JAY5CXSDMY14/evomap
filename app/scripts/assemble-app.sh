#!/bin/bash
# 把 swift build 出来的可执行文件组装成 Evo.app：
#   Contents/MacOS/Evo            SwiftUI 菜单栏外壳
#   Contents/Info.plist           LSUIElement=true（不占 Dock），版本号取 VERSION
#   Contents/Resources/AppIcon.icns  应用图标（调度球，scripts/make-icon.py 生成）
#   Contents/Resources/mate/      表情宿主页；Contents/Resources/vendor/ 表情引擎（aora-bot，固定版本）
#   Contents/Resources/evo/       整套 kit（bin/evo、panel、roles、templates、install.sh…；evo 靠 bin/ 的上一级找 panel/ 和 roles/）
# 用法：scripts/assemble-app.sh <可执行文件> <输出目录> [签名身份，默认 - 即 ad-hoc；传空串跳过签名]
set -euo pipefail
cd "$(dirname "$0")/.."
BIN=${1:?可执行文件路径}
OUT=${2:-build}
SIGN=${3--}
VERSION=$(tr -d '[:space:]' < VERSION)
BUILD=${BUILD_NUMBER:-$(git rev-list --count HEAD 2>/dev/null || echo 1)}
APP="$OUT/Evo.app"
KIT=../kit

[ -d "$APP" ] && chmod -R u+w "$APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/Evo"
sed -e "s/__VERSION__/$VERSION/g" -e "s/__BUILD__/$BUILD/g" Resources/Info.plist.in > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"

# 整套 kit 拷进去，去掉测试、缓存、假工人
cp -R "$KIT" "$APP/Contents/Resources/evo"
rm -rf "$APP/Contents/Resources/evo/tests" "$APP/Contents/Resources/evo/mock"
find "$APP/Contents/Resources/evo" \( -name '__pycache__' -o -name '*.pyc' -o -name '.DS_Store' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
chmod +x "$APP/Contents/Resources/evo/bin/evo" "$APP/Contents/Resources/evo/install.sh"
echo "$VERSION" > "$APP/Contents/Resources/evo/APP_VERSION"
# 表情角色：宿主页 + 第三方引擎（调度球 / 云宝 / 亮亮，许可见 Resources/vendor/NOTICE.md；只许自用，不得公开分发）
cp -R Resources/mate "$APP/Contents/Resources/mate"
cp -R Resources/vendor "$APP/Contents/Resources/vendor"
# 应用图标「调度球」（scripts/make-icon.py 用代码画的，原创；Info.plist 的 CFBundleIconFile 指向它）
cp Resources/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
# bin/ 设成只读：launchd 常驻直接用包里的 evo 时，python 写不进 __pycache__ 就静默跳过，
# 不会改动签过名的包（否则签名失效，Gatekeeper 可能报「已损坏」）
chmod 555 "$APP/Contents/Resources/evo/bin"

if command -v plutil >/dev/null; then plutil -lint "$APP/Contents/Info.plist" >/dev/null; fi
if [ -n "$SIGN" ] && command -v codesign >/dev/null; then
  # ad-hoc 签名（-s -）：自己用够了，第一次打开要右键「打开」；发给别人再换开发者证书
  codesign --force --deep --sign "$SIGN" --timestamp=none "$APP"
  codesign --verify --deep --strict "$APP" && echo "已签名（${SIGN}）"
fi
du -sh "$APP" | awk '{print "Evo.app 大小 " $1}'
echo "$APP"
