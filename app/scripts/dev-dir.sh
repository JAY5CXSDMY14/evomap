#!/bin/sh
# 找一个带 SwiftUI 宏插件（libSwiftUIMacros.dylib）的开发者目录，打印出来；当前就能用或找不到时什么都不打印。
# 原因：xcode-select 指向 CommandLineTools 时没有这个插件，@State 等宏展开不了（Air 试跑 10-21 撞到）。
[ "$(uname)" = Darwin ] || exit 0
has() { [ -n "$(find "$1" -name libSwiftUIMacros.dylib -print -quit 2>/dev/null)" ]; }
cur=$(xcode-select -p 2>/dev/null)
[ -n "$cur" ] && has "$cur" && exit 0
for x in /Applications/Xcode.app /Applications/Xcode-beta.app /Applications/Xcode*.app; do
  d="$x/Contents/Developer"
  [ -d "$d" ] && has "$d" && { echo "$d"; exit 0; }
done
exit 0
