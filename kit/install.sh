#!/bin/bash
# evo 自动循环 · 本机安装（通用，不含任何项目）
#   bash install.sh            只检查，不改任何东西
#   bash install.sh --apply    装：Orca 技能、全局配置（没有才放）、launchd 常驻（evo run --every 30）
#   bash install.sh --apply --link   另在 ~/.local/bin 放一个 evo 软链
# 可以反复跑：已经装好的会跳过。项目不在这里登记，装完用 evo new / evo import。
set -uo pipefail
KIT=$(cd "$(dirname "$0")" && pwd)
APPLY=0; LINK=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --link) LINK=1 ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "不认识的参数：$a"; exit 2 ;;
  esac
done
EVO_DIR=${EVO_DIR:-$HOME/.evoloop}
LOGS=$EVO_DIR/logs
MAGPIE=${MAGPIE_URL:-http://127.0.0.1:3425}
LABEL=com.evoloop.autopilot
PLIST=$HOME/Library/LaunchAgents/$LABEL.plist
ok(){ echo "  ✓ $1"; }; warn(){ echo "  ! $1"; }; info(){ echo "  · $1"; }; bad(){ echo "  ✗ $1"; HARD=1; }
HARD=0

echo "■ 检查环境"
command -v python3 >/dev/null && ok "python3 $(python3 -c 'import sys;print(sys.version.split()[0])')" || bad "没有 python3（evo 跑不起来）"
command -v git >/dev/null && ok "git $(git --version | awk '{print $3}')" || bad "没有 git"
if command -v gh >/dev/null; then
  gh auth status >/dev/null 2>&1 && ok "gh 已登录" || warn "gh 未登录：GitHub issue 入口、留言、建标签会跳过（gh auth login）"
else
  warn "没有 gh：GitHub issue 入口、留言、建标签会跳过"
fi
HAVE_ORCA=0
if command -v orca >/dev/null; then
  HAVE_ORCA=1; ok "orca $(orca --version 2>/dev/null | head -1)"
  orca status --json 2>/dev/null | grep -q '"reachable": *true' && ok "Orca 正在运行" || warn "Orca 没在运行：打开 Orca 应用"
else
  warn "没有 orca 命令：装 Orca 后在 设置 → CLI 里安装命令行（安装第三方工具需老板同意）"
fi
curl -s -m 3 "$MAGPIE/v1/models" >/dev/null 2>&1 && ok "magpie 网关在跑（$MAGPIE）" || warn "magpie 网关没响应（$MAGPIE）：岗位用到模型时才需要"
for a in dsh claude codex; do command -v $a >/dev/null && ok "$a 已装" || info "$a 未装（岗位表用到才需要）"; done

echo "■ 现状"
[ -f "$EVO_DIR/config.json" ] && ok "全局配置 $EVO_DIR/config.json" || info "还没有全局配置，--apply 时从 config.global.example.json 放一份"
if [ "$(uname)" = Darwin ]; then
  [ -f "$PLIST" ] && ok "launchd 常驻已写入 $PLIST" || info "launchd 常驻还没装"
  # 防睡眠：Mac mini 睡着整条流水线都停。只检查、只给建议，绝不替你跑 sudo
  if command -v pmset >/dev/null; then
    SLP=$(pmset -g 2>/dev/null | awk '$1=="sleep"{print $2; exit}')
    DSK=$(pmset -g 2>/dev/null | awk '$1=="disksleep"{print $2; exit}')
    if [ "${SLP:-0}" != 0 ] || [ "${DSK:-0}" != 0 ]; then
      warn "这台 Mac 会睡眠（sleep=${SLP:-?} disksleep=${DSK:-?}）：睡着时接棒、夜审全停。建议自己执行：sudo pmset -a sleep 0 disksleep 0"
    else
      ok "防睡眠已设置（sleep 0、disksleep 0）"
    fi
  fi
else
  info "不是 macOS：跳过 launchd（Linux 上可自己用 systemd/cron 跑：$KIT/bin/evo run --every 30）"
fi
[ -L "$HOME/.local/bin/evo" ] && ok "~/.local/bin/evo 软链已在" || info "~/.local/bin/evo 软链没有（--link 才放）"
echo "■ 需要在 Orca 里手动点一次：设置 → Experimental → 打开 Orchestration；手机 App 扫码配对"

if [ $APPLY = 0 ]; then
  echo "（只检查，没改任何东西。确认无误后：bash $0 --apply [--link]）"
  exit $HARD
fi
[ $HARD = 0 ] || { echo "缺 python3 或 git，先补齐"; exit 1; }

echo "■ 安装"
mkdir -p "$LOGS" "$EVO_DIR/projects"
if [ -f "$EVO_DIR/config.json" ]; then
  ok "全局配置已有，不覆盖"
else
  cp "$KIT/config.global.example.json" "$EVO_DIR/config.json" && ok "已放全局配置 $EVO_DIR/config.json（按本机改模型名）"
fi
if [ $HAVE_ORCA = 1 ]; then
  orca skills install --skill orca-cli --skill orchestration >/dev/null 2>&1 && ok "Orca 技能已装" || warn "Orca 技能没装上（Orca 开着再重跑）"
else
  warn "没有 orca，跳过 Orca 技能"
fi
if [ $LINK = 1 ]; then
  mkdir -p "$HOME/.local/bin"; ln -sfn "$KIT/bin/evo" "$HOME/.local/bin/evo" && ok "~/.local/bin/evo → $KIT/bin/evo"
fi
if [ "$(uname)" = Darwin ]; then
  PY=$(command -v python3)
  xml(){ printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
  ENVX=""
  # 装的时候环境里有就带进常驻进程（plist 只有本人可读）：Telegram、邮件、webhook 密钥、代理（国内连 Telegram 要代理）
  for v in EVO_TG_TOKEN EVO_TG_CHAT EVO_TG_OWNER EVO_SMTP_HOST EVO_SMTP_PORT EVO_SMTP_USER EVO_SMTP_PASS EVO_SMTP_TLS \
           EVO_MAIL_FROM EVO_MAIL_TO EVO_WEBHOOK_SECRET HTTPS_PROXY HTTP_PROXY NO_PROXY; do
    [ -n "${!v:-}" ] && ENVX="$ENVX<key>$v</key><string>$(xml "${!v}")</string>"
  done
  mkdir -p "$(dirname "$PLIST")"
  # install_agent <label> <plist> <说明> <evo 参数...>：内容没变且已加载就跳过
  install_agent(){
    local label=$1 plist=$2 what=$3; shift 3
    local args="" a TMP
    for a in "$@"; do args="$args<string>$a</string>"; done
    TMP=$(mktemp)
    cat > "$TMP" <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>$label</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$KIT/bin/evo</string>$args</array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$LOGS/$what.log</string><key>StandardErrorPath</key><string>$LOGS/$what.log</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin</string>$ENVX</dict>
</dict></plist>
PL
    if [ -f "$plist" ] && cmp -s "$TMP" "$plist" && launchctl list 2>/dev/null | grep -q "$label"; then
      rm -f "$TMP"; ok "$what 常驻没变，跳过"
    else
      mv "$TMP" "$plist"; chmod 600 "$plist"
      launchctl unload "$plist" 2>/dev/null || true
      launchctl load "$plist" && ok "$what 已常驻（日志 $LOGS/$what.log）" || warn "launchctl load $label 失败"
    fi
  }
  install_agent "$LABEL" "$PLIST" autopilot run --every 30
  if [ -n "${EVO_TG_TOKEN:-${TUBU_TG_TOKEN:-}}" ] && [ -n "${EVO_TG_CHAT:-${TUBU_TG_CHAT:-}}" ]; then
    install_agent com.evoloop.bot "$HOME/Library/LaunchAgents/com.evoloop.bot.plist" bot bot
  else
    info "没设 EVO_TG_TOKEN / EVO_TG_CHAT：Telegram 按钮机器人（evo bot）不装"
  fi
fi
echo "完成。下一步登记项目（安装脚本不登记项目）："
echo "  新项目：$KIT/bin/evo new AB --name 名字 --path 目录 [--github 用户/仓库 --create]"
echo "  旧项目：$KIT/bin/evo import TB --name 土布 --path 旧仓库"
echo "  看进度：$KIT/bin/evo status"
echo "  试提醒：$KIT/bin/evo notify-test"
