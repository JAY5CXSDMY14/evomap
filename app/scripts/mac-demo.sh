#!/bin/bash
# 在真的 macOS 桌面上把 Evo.app 跑一遍，拍全屏截图（带菜单栏和窗口外框）+ 录一段 mp4。CI（macos-14）用，本机也能跑。
#   scripts/mac-demo.sh build/Evo.app build/mac-demo
# 用假 evo（scripts/demo/fake-evo.py + demo-state.json），不碰真项目、不联网。
# 驱动方式按顺序试：
#   1) cliclick 真鼠标 / 键盘（应用用 EVO_UITEST_GEOMETRY 把控件坐标写成 JSON，脚本照坐标点）
#   2) 点不动（没有辅助功能权限）→ 往 TCC.db 写授权，再试一次
#   3) 还不行 → 应用自己演（EVO_DEMO=1，按同样的步骤），照样录屏
# 录屏：ffmpeg avfoundation；被拦就退回 screencapture -V。结果写 HOW.txt。
set -o pipefail
cd "$(dirname "$0")/.."
APP=$(cd "$(dirname "${1:-build/Evo.app}")" && pwd)/$(basename "${1:-build/Evo.app}")
OUT=${2:-build/mac-demo}
mkdir -p "$OUT/shots"
OUT=$(cd "$OUT" && pwd)
WORK=$(mktemp -d)
GEO="$WORK/ui.json"
HOW="$OUT/HOW.txt"
: > "$HOW"
note() { echo "$*" | tee -a "$HOW"; }
BUNDLE=com.evoloop.evo
CLICLICK=$(command -v cliclick || true)

note "== Evo mac-demo $(date -u +%FT%TZ)"
sw_vers | tr '\n' ' ' >> "$HOW"; echo >> "$HOW"
system_profiler SPDisplaysDataType 2>/dev/null | grep -E "Resolution|Display Type|Main Display" | sed 's/^ */  /' | tee -a "$HOW"

# ---------- 假 evo 和偏好 ----------
reset_state() { cp scripts/demo/demo-state.json "$WORK/state.json"; }
reset_state
export EVO_DEMO_STATE="$WORK/state.json"
export EVO_NO_NOTIFY=1
chmod +x scripts/demo/fake-evo.py
defaults write $BUNDLE evoPath "$PWD/scripts/demo/fake-evo.py"
defaults write $BUNDLE pythonPath "$(command -v python3)"
defaults write $BUNDLE setupDone -bool true
defaults write $BUNDLE notificationsEnabled -bool false
defaults write $BUNDLE mateCharacter ball
defaults write $BUNDLE appearance light
defaults delete $BUNDLE "NSWindow Frame Evo.main" 2>/dev/null || true
mkdir -p "$HOME/.evoloop"
# CI 上关掉免打扰（不然半夜跑的录屏里角色在睡觉）；本机跑不动你的配置
if [ -n "${CI:-}" ] || [ ! -f "$HOME/.evoloop/config.json" ]; then echo '{"notify": {"quiet_hours": {}}}' > "$HOME/.evoloop/config.json"; fi

# ---------- 录屏 ----------
REC_PID=""; REC_KIND=""
start_rec() {
  if command -v ffmpeg >/dev/null; then
    local idx
    idx=$(ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 | grep -m1 "Capture screen" | sed -E 's/.*\[([0-9]+)\] Capture screen.*/\1/')
    note "ffmpeg 屏幕设备：${idx:-没找到}"
    if [ -n "$idx" ]; then
      ffmpeg -nostdin -y -hide_banner -loglevel warning -f avfoundation -capture_cursor 1 -capture_mouse_clicks 1 -framerate 24 \
        -i "${idx}:none" -vf "scale='min(1600,iw)':-2,format=yuv420p" -c:v libx264 -preset veryfast -crf 30 -movflags +faststart \
        "$OUT/evo-demo.mp4" > "$OUT/ffmpeg.log" 2>&1 &
      REC_PID=$!
      sleep 4
      if kill -0 $REC_PID 2>/dev/null; then REC_KIND=ffmpeg; note "录屏：ffmpeg avfoundation"; return; fi
      note "ffmpeg 录屏起不来：$(tail -3 "$OUT/ffmpeg.log" | tr '\n' ' ')"
    fi
  fi
  screencapture -x -V 150 "$WORK/rec.mov" > "$WORK/sc.log" 2>&1 &
  REC_PID=$!; REC_KIND=screencapture
  sleep 2
  note "录屏：screencapture -V（ffmpeg 不可用时的退路）"
}
stop_rec() {
  [ -n "$REC_PID" ] || return
  if [ "$REC_KIND" = ffmpeg ]; then kill -INT $REC_PID 2>/dev/null; else kill -INT $REC_PID 2>/dev/null; fi
  for _ in $(seq 1 30); do kill -0 $REC_PID 2>/dev/null || break; sleep 0.5; done
  kill -9 $REC_PID 2>/dev/null || true
  if [ "$REC_KIND" = screencapture ] && [ -f "$WORK/rec.mov" ] && command -v ffmpeg >/dev/null; then
    ffmpeg -nostdin -y -loglevel warning -i "$WORK/rec.mov" -vf "scale='min(1600,iw)':-2,format=yuv420p" -c:v libx264 -preset veryfast -crf 30 "$OUT/evo-demo.mp4" || true
  elif [ "$REC_KIND" = screencapture ] && [ -f "$WORK/rec.mov" ]; then
    cp "$WORK/rec.mov" "$OUT/evo-demo.mov"
  fi
  ls -la "$OUT"/evo-demo.* 2>/dev/null | tee -a "$HOW"
}

# ---------- 应用 ----------
APP_PID=""
launch() {   # $@ = 额外环境变量
  pkill -x Evo 2>/dev/null; sleep 1
  rm -f "$GEO"
  env "$@" EVO_UITEST_GEOMETRY="$GEO" "$APP/Contents/MacOS/Evo" >> "$OUT/app.log" 2>&1 &
  APP_PID=$!
  for _ in $(seq 1 60); do [ -s "$GEO" ] && grep -q status-item "$GEO" && break; sleep 0.25; done
  sleep 4    # 等第一轮 status 读完、角色加载
}

pt() {   # 控件中心坐标 x,y；没有就空
  python3 - "$GEO" "$1" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1])); v = d.get(sys.argv[2])
    print("%d,%d" % (v["cx"], v["cy"]) if isinstance(v, dict) and "cx" in v else "")
except Exception:
    print("")
PY
}
waitpt() { local p; for _ in $(seq 1 40); do p=$(pt "$1"); [ -n "$p" ] && { echo "$p"; return 0; }; sleep 0.25; done; return 1; }
geo() { python3 -c "import json,sys;print(json.load(open('$GEO')).get('$1',''))" 2>/dev/null; }
shot() { screencapture -x -C "$OUT/shots/$1.png" && echo "  📸 $1"; }
click() {
  local p; p=$(waitpt "$1") || { note "  ✗ 找不到控件 $1"; return 1; }
  "$CLICLICK" -e 300 "m:$p" >/dev/null; sleep 0.2
  "$CLICLICK" "c:$p" >/dev/null
  echo "  → 点 $1 ($p)"
}
paste_text() { printf '%s' "$1" | pbcopy; "$CLICLICK" kd:cmd t:v ku:cmd >/dev/null; }
key() { "$CLICLICK" "$@" >/dev/null; }

can_drive() {   # 鼠标真的能被挪动、点开弹窗吗（点开的弹窗留着，drive 接着用）
  [ -n "$CLICLICK" ] || { note "没有 cliclick"; return 1; }
  "$CLICLICK" m:400,400 >/dev/null 2>&1; sleep 0.3
  local p; p=$("$CLICLICK" p 2>/dev/null | tail -1)
  note "  鼠标挪到 400,400 后读回：$p"
  open_popover && return 0
  note "  点了菜单栏图标，弹窗没出来"
  return 1
}

popover_open() { [ -n "$(pt pop-open-window)" ]; }
open_popover() {   # 弹窗是开关式的：先看是不是已经开着，没开再点，最多点两次
  local _i _j
  for _i in 1 2; do
    popover_open && return 0
    click status-item || return 1
    for _j in $(seq 1 16); do popover_open && return 0; sleep 0.25; done
  done
  return 1
}
window_open() { [ -n "$(pt win-sidebar-inbox)" ]; }
evo_front() {     # 键盘事件只在 Evo 在最前面时发，免得打进 Finder（应用自己报 NSApp.isActive）
  sleep 0.35; [ "$(geo active)" = "1" ]
}

tcc_grant() {
  note "写 TCC.db 授权（辅助功能 / 发事件 / 录屏）…"
  local now; now=$(date +%s)
  for db in "$HOME/Library/Application Support/com.apple.TCC/TCC.db" "/Library/Application Support/com.apple.TCC/TCC.db"; do
    [ -f "$db" ] || continue
    for client in "$CLICLICK" /bin/bash /bin/sh /usr/bin/osascript "$(command -v ffmpeg || echo /usr/bin/true)" /usr/sbin/screencapture "$APP/Contents/MacOS/Evo"; do
      for svc in kTCCServiceAccessibility kTCCServicePostEvent kTCCServiceScreenCapture; do
        sudo sqlite3 "$db" "INSERT OR REPLACE INTO access (service, client, client_type, auth_value, auth_reason, auth_version, indirect_object_identifier, flags, last_modified) VALUES ('$svc', '$client', 1, 2, 4, 1, 'UNUSED', 0, $now);" 2>>"$WORK/tcc.log" || true
      done
    done
  done
  sudo killall tccd 2>/dev/null || true
  tail -3 "$WORK/tcc.log" 2>/dev/null | sed 's/^/  tcc: /' | tee -a "$HOW"
  sleep 2
}

# ---------- 驱动（真鼠标） ----------
drive() {
  local fails=0
  sleep 1.2; shot 02-popover
  click pop-open-window || fails=$((fails+1))
  for _ in $(seq 1 30); do window_open && break; sleep 0.25; done
  if ! window_open; then     # 再试一次：重新点开弹窗再点按钮
    note "  窗口没出来，重试"
    open_popover && click pop-open-window
    for _ in $(seq 1 30); do window_open && break; sleep 0.25; done
  fi
  window_open || { note "  ✗ 主窗口打不开"; return 1; }
  sleep 2.6; shot 03-window
  # 在窗口里晃晃鼠标：角色跟着看
  local m; m=$(pt win-sidebar-inbox)
  if [ -n "$m" ]; then
    local mx=${m%,*} my=${m#*,}
    key -e 600 "m:$((mx+520)),$((my-140))"; key -e 600 "m:$((mx+80)),$((my+320))"; key -e 500 "m:$((mx-30)),$((my-170))"
  fi
  click win-gate-0-approve || fails=$((fails+1)); sleep 0.22; shot 04-approve-fly; sleep 2.2; shot 05-approved
  click win-gate-0-reject || fails=$((fails+1)); waitpt win-gate-0-send >/dev/null; sleep 0.5
  if evo_front; then paste_text "手机上按钮太挤，再大一圈"; fi; sleep 0.9; shot 06-reject-words
  click win-gate-0-send || fails=$((fails+1)); sleep 2.2; shot 07-rejected
  click win-sidebar-project-TB || fails=$((fails+1)); sleep 2.0; shot 08-project
  click win-item-0 || fails=$((fails+1)); sleep 2.6; shot 09-item-timeline
  # v0.4.0 团队页：岗位卡片 → 输入框「把验收换成 group/evo-verify」→ 确认卡 → 确认
  click win-sidebar-team || fails=$((fails+1)); sleep 2.6; shot 09b-team
  click composer-field || fails=$((fails+1)); sleep 0.4
  if evo_front; then paste_text "把验收换成 group/evo-verify"; fi; sleep 0.5
  click composer-send || fails=$((fails+1)); waitpt team-confirm-yes >/dev/null; sleep 1.2; shot 09c-team-confirm
  click team-confirm-yes || fails=$((fails+1)); sleep 2.4; shot 09d-team-changed
  click win-sidebar-project-TB || true; sleep 1.0; click win-item-0 || true; sleep 1.6
  if evo_front; then
    key kd:cmd t:k ku:cmd; sleep 1.0
    if [ -n "$(pt palette-field)" ]; then paste_text "深色"; sleep 1.0; shot 10-palette; key kp:return; else note "  ✗ ⌘K 面板没出来"; fails=$((fails+1)); fi
  else note "  ✗ Evo 不在最前面，跳过键盘步骤"; fails=$((fails+1)); fi
  sleep 2.4; shot 11-dark-item
  click win-sidebar-inbox || fails=$((fails+1)); sleep 1.4; shot 12-dark-inbox
  click composer-field || fails=$((fails+1)); sleep 0.4
  if evo_front; then paste_text "注册页在手机上按钮太挤了"; fi; sleep 0.6
  click composer-send || fails=$((fails+1)); sleep 3.6; shot 13-composer-reply
  open_popover || fails=$((fails+1)); sleep 1.8; shot 14-popover-dark
  popover_open && click status-item; sleep 0.6
  note "真鼠标驱动完成，失败 $fails 处；最后状态：$(geo selection) · 卡片 $(geo cards) · 深色 $(geo dark)"
  [ $fails -le 4 ]
}

demo_mode() {
  note "退回应用自演模式（EVO_DEMO=1）"
  reset_state
  launch EVO_DEMO=1 EVO_DEMO_SHOTS="$OUT/shots"
  for _ in $(seq 1 120); do [ -f "$OUT/shots/DONE" ] && break; sleep 0.5; done
  rm -f "$OUT/shots/DONE"
  note "自演结束：$(ls "$OUT/shots" | wc -l | tr -d ' ') 张"
}

start_rec
launch
shot 01-desktop
MODE=""
if can_drive; then MODE=cliclick
else
  tcc_grant
  launch
  shot 01-desktop
  if can_drive; then MODE="cliclick（写 TCC.db 后）"; fi
fi
if [ -n "$MODE" ]; then
  note "驱动方式：$MODE"
  if ! drive; then
    note "真鼠标驱动失败太多：改用应用自演补拍"
    rm -f "$OUT"/shots/*.png
    demo_mode
    MODE="$MODE → demo"
  fi
else
  note "两次都点不动：改用应用自演"
  demo_mode
  MODE=demo
fi
sleep 1
stop_rec
pkill -x Evo 2>/dev/null || true
note "截图："; ls -1 "$OUT/shots" | sed 's/^/  /' | tee -a "$HOW"
[ "$(ls "$OUT/shots" | wc -l)" -gt 3 ] || { note "截图太少，算失败"; exit 1; }
