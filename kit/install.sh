#!/bin/bash
# evo 自动循环 · 本机安装（通用，不含任何项目）
#   bash install.sh            只检查，不改任何东西
#   bash install.sh --apply    装：Orca 技能、全局配置（没有才放）、launchd 常驻（evo run --every 30）
#   bash install.sh --apply --link   另在 ~/.local/bin 放一个 evo 软链
#   第十八轮（自维护）：--apply 时把这套 kit 拷成 ~/.evoloop/releases/<版本>/，~/.evoloop/current 软链指向它，常驻进程跑 current；
#   另装看门狗 ~/.evoloop/guard/evo-guard.sh（launchd 每分钟一次，自升级后 10 分钟没心跳 / 自检失败就切回上一版）。
#   bash install.sh --apply --dev    开发用：常驻进程直接跑这个目录（不建 releases / current，不装看门狗）
# 可以反复跑：已经装好的会跳过。项目不在这里登记，装完用 evo new / evo import。
set -uo pipefail
KIT=$(cd "$(dirname "$0")" && pwd)
APPLY=0; LINK=0; DEV=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --link) LINK=1 ;;
    --dev) DEV=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
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

# 常驻进程用的 PATH（Air 试跑 10-21：launchd 不读 ~/.zshrc，claude/dsh 装在 ~/.claude/local、npm 全局等目录时后台找不到）。
# 取你登录 shell 的 PATH + 常用目录，去重、只留存在的目录；本脚本的检查也用它，结果和后台一致。可用 EVO_PATH=… 自己指定。
LPATH=${EVO_PATH:-}
if [ -z "$LPATH" ]; then
  SHP=$("${SHELL:-/bin/zsh}" -ilc 'printf "\n__EVOPATH=%s\n" "$PATH"' </dev/null 2>/dev/null | sed -n 's/^__EVOPATH=//p' | tail -1)
  LPATH=$(printf '%s' "$PATH:$SHP:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin" | tr ':' '\n' |
    awk 'NF && !/[<>&]/ && !seen[$0]++' | while read -r d; do [ -d "$d" ] && printf '%s:' "$d"; done)
  LPATH=${LPATH%:}
fi
export PATH="$LPATH"

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
if curl -s -m 3 "$MAGPIE/v1/models" >/dev/null 2>&1; then
  ok "magpie 网关在跑（$MAGPIE）"
  # 施工/验收模型（可以是 magpie 组名）在不在 magpie 列表里、两边有没有重叠：只警告，不拦安装
  if command -v python3 >/dev/null && [ -f "$EVO_DIR/config.json" ]; then
    python3 "$KIT/bin/evo" models 2>&1 || true
  fi
else
  warn "magpie 网关没响应（$MAGPIE）：岗位用到模型时才需要"
fi
for a in dsh claude codex; do command -v $a >/dev/null && ok "$a 已装" || info "$a 未装（岗位表用到才需要）"; done

echo "■ 现状"
info "常驻进程的 PATH：$LPATH"
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
# 第十八轮：装成一个版本（releases/<版本>/ + current 软链）。版本名 = 仓库提交号，没有 git 时用 App 版本或日期
RUN_KIT=$KIT
if [ $DEV = 0 ]; then
  SRC=""
  if git -C "$KIT/.." rev-parse --git-dir >/dev/null 2>&1; then
    SRC=$(cd "$KIT/.." && pwd)
    VER=$(git -C "$SRC" rev-parse --short=10 HEAD)
    git -C "$SRC" diff --quiet HEAD -- kit 2>/dev/null || VER="$VER-dirty$(date +%m%d%H%M)"
  elif [ -f "$KIT/APP_VERSION" ]; then
    VER="app-$(tr -d '[:space:]' < "$KIT/APP_VERSION")"
  else
    VER="local-$(date +%Y%m%d%H%M)"
  fi
  REL="$EVO_DIR/releases/$VER"
  if [ -d "$REL" ]; then
    ok "版本 $VER 已在 $REL"
  else
    mkdir -p "$EVO_DIR/releases"
    TMPR="$REL.tmp$$"; rm -rf "$TMPR"; mkdir -p "$TMPR"
    (cd "$KIT" && tar --exclude tests --exclude mock --exclude __pycache__ --exclude '*.pyc' -cf - .) | (cd "$TMPR" && tar -xf -)
    [ -n "$SRC" ] && echo "$SRC" > "$TMPR/SOURCE"
    echo "$VER" > "$TMPR/VERSION"
    mv "$TMPR" "$REL" && ok "已装版本 $VER → $REL"
  fi
  if [ -L "$EVO_DIR/current" ] && [ "$(readlink "$EVO_DIR/current")" != "releases/$VER" ]; then
    basename "$(readlink "$EVO_DIR/current")" > "$EVO_DIR/releases/PREVIOUS"
  fi
  python3 -c 'import os,sys; t=sys.argv[1]+".new"; os.path.lexists(t) and os.remove(t); os.symlink(sys.argv[2], t); os.replace(t, sys.argv[1])' \
    "$EVO_DIR/current" "releases/$VER" && ok "current → releases/$VER（上一版记在 releases/PREVIOUS）"
  RUN_KIT="$EVO_DIR/current"
  # 看门狗：拷到 guard/（不在 releases 里，自升级碰不到它）
  mkdir -p "$EVO_DIR/guard"; cp "$KIT/selfmaint/evo-guard.sh" "$EVO_DIR/guard/evo-guard.sh"; chmod 755 "$EVO_DIR/guard/evo-guard.sh"
  ok "看门狗脚本 $EVO_DIR/guard/evo-guard.sh"
else
  info "--dev：常驻进程直接跑 $KIT（不建 releases，不装看门狗）"
fi
if [ -f "$EVO_DIR/config.json" ]; then
  ok "全局配置已有，不覆盖"
else
  cp "$KIT/config.global.example.json" "$EVO_DIR/config.json" && ok "已放全局配置 $EVO_DIR/config.json（按本机改模型名）"
fi
if [ $HAVE_ORCA = 1 ]; then
  # Air 试跑 10-21：装技能要 Node 22+（skills 包用 fs/promises.glob）；PATH 里是 node 20 时会失败，原来的提示误导成「Orca 没开」
  NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)
  if [ "${NODE_MAJOR:-0}" -lt 22 ] 2>/dev/null; then
    warn "Orca 技能要 Node 22 以上，PATH 里的 node 是 $(node --version 2>/dev/null || echo 没有)：装/切到 Node 22 后重跑 --apply（例 brew install node）"
  elif OUT=$(orca skills install --skill orca-cli --skill orchestration 2>&1); then
    ok "Orca 技能已装"
  else
    warn "Orca 技能没装上：$(printf '%s' "$OUT" | grep -v '^\s*at ' | tail -n 2 | tr '\n' ' ')"
  fi
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
  # PYTHONDONTWRITEBYTECODE=1：常驻进程不在套件目录里写 __pycache__（装在应用包里时包内文件不能变，否则签名失效）
  install_agent(){
    local label=$1 plist=$2 what=$3; shift 3
    local args="" a TMP
    for a in "$@"; do args="$args<string>$a</string>"; done
    TMP=$(mktemp)
    cat > "$TMP" <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>$label</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$RUN_KIT/bin/evo</string>$args</array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$LOGS/$what.log</string><key>StandardErrorPath</key><string>$LOGS/$what.log</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>$LPATH</string><key>PYTHONDONTWRITEBYTECODE</key><string>1</string><key>PYTHONUNBUFFERED</key><string>1</string>$ENVX</dict>
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
  if [ $DEV = 0 ]; then                # 第十八轮：看门狗，每 60 秒一次（只在自升级后的观察期里动手）
    GP="$HOME/Library/LaunchAgents/com.evoloop.guard.plist"; TMPG=$(mktemp)
    cat > "$TMPG" <<PL
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.evoloop.guard</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>$EVO_DIR/guard/evo-guard.sh</string></array>
<key>StartInterval</key><integer>60</integer><key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>$LOGS/guard.log</string><key>StandardErrorPath</key><string>$LOGS/guard.log</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>$LPATH</string><key>EVO_DIR</key><string>$EVO_DIR</string>$ENVX</dict>
</dict></plist>
PL
    if [ -f "$GP" ] && cmp -s "$TMPG" "$GP" && launchctl list 2>/dev/null | grep -q com.evoloop.guard; then
      rm -f "$TMPG"; ok "看门狗常驻没变，跳过"
    else
      mv "$TMPG" "$GP"; chmod 600 "$GP"; launchctl unload "$GP" 2>/dev/null || true
      launchctl load "$GP" && ok "看门狗已常驻（每分钟一次，日志 $LOGS/guard.log）" || warn "launchctl load com.evoloop.guard 失败"
    fi
  fi
  if [ -n "${EVO_TG_TOKEN:-${TUBU_TG_TOKEN:-}}" ] && [ -n "${EVO_TG_CHAT:-${TUBU_TG_CHAT:-}}" ]; then
    install_agent com.evoloop.bot "$HOME/Library/LaunchAgents/com.evoloop.bot.plist" bot bot
  else
    info "没设 EVO_TG_TOKEN / EVO_TG_CHAT：Telegram 按钮机器人（evo bot）不装"
  fi
fi
# 第十七轮（老板决定②）：已登记、还在老板工作副本里合并的项目，提示切到 evo 专用克隆
for cfg in "${EVO_HOME:-$HOME/.evoloop/projects}"/*/config.json; do
  [ -f "$cfg" ] || continue
  code=$(basename "$(dirname "$cfg")")
  if ! grep -q '"clone": *true' "$cfg"; then
    info "$code 还在你的工作副本里合并：$KIT/bin/evo -p $code relocate 切到 ~/.evoloop/repos/$code（之后 evo 不碰你的副本）"
  fi
done
echo "完成。下一步登记项目（安装脚本不登记项目）："
echo "  新项目：${RUN_KIT:-$KIT}/bin/evo new AB --name 名字 --path 目录 [--github 用户/仓库 --create]"
echo "  旧项目：${RUN_KIT:-$KIT}/bin/evo import TB --name 土布 --path 旧仓库   （有远端时 evo 在 ~/.evoloop/repos/TB 自己克隆一份，只在那里合并推送；不要就加 --in-place）"
echo "  已登记的老项目切到专用克隆：${RUN_KIT:-$KIT}/bin/evo -p TB relocate"
echo "  每件上限：${RUN_KIT:-$KIT}/bin/evo limits   （决策岗返工 2 次、派工 12 次、累计 6 小时；面板「每件上限」可改）"
echo "  看进度：${RUN_KIT:-$KIT}/bin/evo status"
echo "  试提醒：${RUN_KIT:-$KIT}/bin/evo notify-test"
