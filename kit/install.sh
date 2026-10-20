#!/bin/bash
# 土布自动循环 · Mac mini 一键安装（默认只检查，加 --apply 才写入）
set -euo pipefail
KIT=$(cd "$(dirname "$0")" && pwd); APPLY=${1:-}
ok(){ echo "  ✓ $1"; }; no(){ echo "  ✗ $1"; MISS=1; }; MISS=0
echo "■ 检查"
command -v orca >/dev/null && ok "Orca 命令行 $(orca --version 2>/dev/null | head -1)" || no "没有 orca 命令：装 Orca 后在 设置 → CLI 里安装命令行（安装第三方工具需老板同意）"
orca status --json 2>/dev/null | grep -q '"reachable": true' && ok "Orca 正在运行" || no "Orca 没在运行：打开 Orca 应用"
curl -s -m 3 http://127.0.0.1:3425/v1/models >/dev/null && ok "magpie 网关在跑" || no "magpie 网关没响应（127.0.0.1:3425）"
command -v gh >/dev/null && gh auth status >/dev/null 2>&1 && ok "GitHub 已登录" || no "gh 未登录"
for a in dsh claude codex; do command -v $a >/dev/null && ok "$a 已装" || echo "  · $a 未装（岗位表用到才需要）"; done
[ -f "$KIT/config.json" ] && ok "config.json 已就位" || { echo "  · 还没有 config.json，--apply 时从样例生成"; }
echo "■ 需要在 Orca 里手动点一次：设置 → Experimental → 打开 Orchestration；手机 App 扫码配对"
[ "$APPLY" = "--apply" ] || { echo "（只检查。确认无误后：bash install.sh --apply）"; exit $MISS; }
[ $MISS = 0 ] || { echo "有缺项，先补齐"; exit 1; }
[ -f "$KIT/config.json" ] || cp "$KIT/config.example.json" "$KIT/config.json"
orca skills install --skill orca-cli --skill orchestration >/dev/null && ok "Orca 技能已装"
orca repo add --path "$(python3 -c "import json;print(json.load(open('$KIT/config.json'))['repo'])")" --json >/dev/null && ok "仓库已登记到 Orca"
P=~/Library/LaunchAgents/com.evoloop.autopilot.plist
cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.evoloop.autopilot</string>
<key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$KIT/bin/evo</string><string>run</string><string>--every</string><string>30</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$KIT/.state/autopilot.log</string><key>StandardErrorPath</key><string>$KIT/.state/autopilot.log</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin</string></dict>
</dict></plist>
PL
mkdir -p "$KIT/.state"; launchctl unload "$P" 2>/dev/null || true; launchctl load "$P" && ok "接棒器已常驻（每 30 秒一轮）"
echo "完成。看进度：$KIT/bin/evo status"
