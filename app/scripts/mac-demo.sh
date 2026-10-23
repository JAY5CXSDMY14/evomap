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
# 功能开关 / 事件流交给包里的真 evo；EVO_HOME 放临时目录，不碰本机的（插件演示第二十四轮删了）
export EVO_REAL_EVO="$APP/Contents/Resources/evo/bin/evo"
export EVO_HOME="$WORK/evo/projects"
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$EVO_HOME"
mkdir -p "$HOME/.evoloop"
# runner 默认可能开着「减弱动态效果」（调度球就只画静态帧、不跟鼠标）：记下来，试着关掉；关不掉应用也会因 EVO_DEMO_MOTION=1 照样动
note "减弱动态效果（录屏前）：$(defaults read com.apple.universalaccess reduceMotion 2>&1 | tail -1)"
defaults write com.apple.universalaccess reduceMotion -bool false 2>/dev/null || true
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
  env "$@" EVO_DEMO_MOTION=1 EVO_STALL_DIR="$OUT" EVO_UITEST_GEOMETRY="$GEO" "$APP/Contents/MacOS/Evo" >> "$OUT/app.log" 2>&1 &
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
# 等控件停稳（滚动 / 展开动画结束）：连续两次读到同一坐标才算（最多 6 秒）
waitstable() { local a b; a=$(pt "$1"); for _ in $(seq 1 20); do sleep 0.35; b=$(pt "$1"); [ -n "$b" ] && [ "$a" = "$b" ] && return 0; a=$b; done; return 1; }
geo() { python3 -c "import json,sys;print(json.load(open('$GEO')).get('$1',''))" 2>/dev/null; }
shot() { screencapture -x -C "$OUT/shots/$1.png" && echo "  📸 $1"; }
# 第十九轮：探点文件要是新的才信它的坐标（主线程忙的那几秒文件不更新，按旧坐标点会点到别的控件上）
waitfresh() {
  local _i age
  for _i in $(seq 1 48); do
    age=$(( $(date +%s) - $(stat -f %m "$GEO" 2>/dev/null || echo 0) ))
    [ "$age" -le 1 ] && return 0
    sleep 0.25
  done
  note "  ⚠ 探点 12 秒没更新（主线程忙），照旧坐标继续"; return 1
}
click() {
  waitfresh || true
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
  sleep 0.35; waitfresh || true; [ "$(geo active)" = "1" ]
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

# ---------- v0.5.0 调度球：眼睛跟鼠标（远 → 慢慢靠近 → 绕一圈 → 贴近 → 离开）----------
gaze_note() { note "    眼睛（mate-gaze）：$(geo mate-gaze | tr -d '\n ')"; }
eyes_demo() {
  local m; m=$(waitpt win-mate) || { note "  ✗ 找不到调度球（win-mate）"; return 1; }
  local cx=${m%,*} cy=${m#*,} r a x y i
  note "  调度球中心 ${m}（球径 58，感应半径约 174）"
  key -e 400 "m:$((cx+620)),$((cy+380))"; sleep 1.4; shot 03a-eyes-far; gaze_note
  # 慢慢移近：从右下远处走到右侧 70 点
  for i in 1 2 3 4 5 6 7 8; do
    x=$((cx + 620 - i * 550 / 8)); y=$((cy + 380 - i * 380 / 8))
    key -e 220 "m:$x,$y"; sleep 0.12
  done
  key -e 300 "m:$((cx+70)),$((cy-10))"; sleep 1.0; shot 03b-eyes-near-right; gaze_note
  # 绕一圈（半径 95 点，每 30° 一步），停在左下拍一张
  r=95
  for a in 0 30 60 90 120 150 180 210 240 270 300 330 360; do
    read -r x y < <(python3 -c "import math;a=math.radians($a);print(round($cx+$r*math.cos(a)), round($cy-$r*math.sin(a)))")
    key -e 160 "m:$x,$y"; sleep 0.1
    if [ "$a" = 180 ]; then sleep 0.9; shot 03c-eyes-circle-left; gaze_note; fi
    if [ "$a" = 270 ]; then sleep 0.9; shot 03d-eyes-circle-below; gaze_note; fi
  done
  # 贴近：惊喜（眼睛微放大、身体一缩）
  # 进「很近」时会眨一下（约 0.5 秒），等眨完再拍，拍到的是放大的眼睛和缩一下的身体
  key -e 300 "m:$((cx+18)),$((cy-12))"; sleep 1.8; shot 03e-eyes-very-near; gaze_note
  # 离开：眼睛弹回居中
  key -e 700 "m:$((cx+700)),$((cy+300))"; sleep 1.4; shot 03f-eyes-away; gaze_note
}

icon_shots() {   # 应用图标：Dock（主窗口开着时 Dock 有 Evo）+ Finder 里的 Evo.app
  local sw sh
  sw=$(python3 -c "import json;print(int(json.load(open('$GEO'))['screen']['w']))" 2>/dev/null || echo 0)
  sh=$(python3 -c "import json;print(int(json.load(open('$GEO'))['screen']['h']))" 2>/dev/null || echo 0)
  shot 15-dock
  if [ "$sw" -gt 0 ]; then screencapture -x -R "0,$((sh-110)),$sw,110" "$OUT/shots/15b-dock-strip.png" && echo "  📸 15b-dock-strip"; fi
  # 图标文件本身（sips 能读说明 icns 格式没问题）
  sips -s format png "$APP/Contents/Resources/AppIcon.icns" --out "$OUT/shots/AppIcon-from-icns.png" >/dev/null 2>&1 \
    && note "  sips 读 AppIcon.icns：$(sips -g pixelWidth "$OUT/shots/AppIcon-from-icns.png" | tail -1 | tr -s ' ')" \
    || note "  ✗ sips 读不了 AppIcon.icns"
}

finder_icon_shot() {
  open -R "$APP" 2>/dev/null || return 0
  sleep 2.5; shot 16-finder-icon
  osascript -e 'tell application "Finder" to close every window' >/dev/null 2>&1 || true
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
  icon_shots
  eyes_demo || fails=$((fails+1))
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
  # v0.7.0 功能开关：设置 → 功能，关掉「团队 / 模型协调」→ 侧栏「团队」消失（真 evo feature off team）
  click win-sidebar-settings || fails=$((fails+1)); waitpt settings-feature-team >/dev/null; sleep 1.6; waitstable settings-feature-team
  click settings-feature-team || fails=$((fails+1))
  local t_off; t_off=$(date +%s)
  for _ in $(seq 1 24); do [ -z "$(pt win-sidebar-team)" ] && break; sleep 0.5; done
  note "    关 team 到侧栏变化：$(( $(date +%s) - t_off )) 秒"
  note "    探点文件 $(( $(date +%s) - $(stat -f %m "$GEO" 2>/dev/null || echo 0) )) 秒前更新"
  sleep 1.2; shot 09h-features-team-off
  if [ -n "$(pt win-sidebar-team)" ]; then note "  ✗ 关了 team，侧栏「团队」还在"; fails=$((fails+1)); else note "  ✓ 侧栏「团队」已消失"; fi
  python3 "$EVO_REAL_EVO" feature list 2>&1 | grep -E "team|预设" | sed 's/^/    evo: /' | tee -a "$HOW"
  # v0.7.0 自动表单：展开「每件上限」，派工次数填 2000（schema 最大 1000）→ 红字；再填 30 → 存好
  click feature-expand-item-caps || fails=$((fails+1)); sleep 1.2
  waitpt feature-field-item-caps-item_hard_runs >/dev/null; sleep 0.8; waitstable feature-field-item-caps-item_hard_runs || note "  ⚠ 表单还在动"
  note "    表单输入框位置：$(pt feature-field-item-caps-item_hard_runs)"
  click feature-field-item-caps-item_hard_runs || fails=$((fails+1)); sleep 0.3
  if evo_front; then key kd:cmd t:a ku:cmd; paste_text "2000"; sleep 0.3; key kp:return; fi
  waitpt feature-error-item-caps-item_hard_runs >/dev/null || { note "  ✗ 没出红字"; fails=$((fails+1)); }; sleep 0.8; shot 09i-feature-form-error
  click feature-field-item-caps-item_hard_runs || true; sleep 0.3
  if evo_front; then key kd:cmd t:a ku:cmd; paste_text "30"; sleep 0.3; key kp:return; fi
  sleep 2.4; shot 09j-feature-form-saved
  python3 "$EVO_REAL_EVO" feature list --json 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);print('    evo: item-caps', [f['config'] for f in d['features'] if f['id']=='item-caps'])" | tee -a "$HOW"
  # v0.7.0 错误边界：假 evo 的 log 弄坏 → 打开件详情 → 「这页出错了 + 重试」；修好后点重试
  python3 scripts/demo/fake-evo.py _demo break log | tee -a "$HOW"
  click win-sidebar-project-TB || fails=$((fails+1)); sleep 1.4
  click win-item-0 || fails=$((fails+1)); waitpt page-error-retry >/dev/null || { note "  ✗ 没出错误卡片"; fails=$((fails+1)); }; sleep 1.2; shot 09k-page-error
  python3 scripts/demo/fake-evo.py _demo fix log | tee -a "$HOW"
  click page-error-retry || fails=$((fails+1)); sleep 2.4; shot 09l-page-error-retried
  if [ -n "$(pt page-error-card)" ]; then note "  ✗ 重试后错误卡片还在"; fails=$((fails+1)); fi
  # 第十九轮：首页只放「等你处理」，其余收成一行（点开看项目）
  click win-sidebar-inbox || fails=$((fails+1)); sleep 1.6; shot 19a-home-light
  [ -n "$(pt home-projects-toggle)" ] || note "  ✗ 首页没有「其余」那一行"
  click home-projects-toggle || fails=$((fails+1)); sleep 1.4; shot 19b-home-projects
  click home-projects-toggle || true; sleep 0.8
  # 第十九轮：⌘K 分组 + 直接跳到件 → 时间线 +「为什么卡住」
  if evo_front; then
    key kd:cmd t:k ku:cmd; sleep 1.0
    if [ -n "$(pt palette-field)" ]; then
      shot 19c-palette-sections
      paste_text "EV-NOTI"; sleep 0.9; shot 19d-palette-item; waitfresh || true; key kp:return; sleep 2.6; waitfresh || true
      waitpt item-diagnosis >/dev/null && note "  ✓ ⌘K 跳到件详情，有「为什么卡住」" || { note "  ✗ ⌘K 没跳到件详情"; fails=$((fails+1)); }
      shot 19e-item-stuck-light
    else note "  ✗ ⌘K 面板没出来"; fails=$((fails+1)); fi
  fi
  click win-sidebar-project-TB || true; sleep 1.0; click win-item-0 || true; sleep 1.6
  if evo_front; then
    key kd:cmd t:k ku:cmd; sleep 1.0
    if [ -n "$(pt palette-field)" ]; then
      paste_text "深色"; sleep 1.0; shot 10-palette; key kp:return; sleep 1.5; waitfresh || true
      if [ -n "$(pt palette-field)" ]; then note "  ⚠ 回车后面板还开着，再按一次 enter"; key kp:enter; sleep 0.8; fi
    else note "  ✗ ⌘K 面板没出来"; fails=$((fails+1)); fi
  else note "  ✗ Evo 不在最前面，跳过键盘步骤"; fails=$((fails+1)); fi
  sleep 2.4; shot 11-dark-item
  # 第十九轮：深色下设置页的开关（关着的 team 开关底色要看得清）
  click win-sidebar-settings || fails=$((fails+1)); waitpt settings-feature-team >/dev/null; sleep 1.4; shot 11b-dark-settings-toggles
  click win-sidebar-inbox || fails=$((fails+1)); sleep 1.4; shot 12-dark-inbox
  click composer-field || fails=$((fails+1)); sleep 0.4
  if evo_front; then paste_text "注册页在手机上按钮太挤了"; fi; sleep 0.6
  click composer-send || fails=$((fails+1)); sleep 3.6; shot 13-composer-reply
  if evo_front; then
    key kd:cmd t:k ku:cmd; sleep 1.0
    if [ -n "$(pt palette-field)" ]; then
      paste_text "EV-NOTI"; sleep 0.8; waitfresh || true; key kp:return; sleep 2.6; waitfresh || true
      waitpt item-diagnosis >/dev/null && note "  ✓ 深色下 ⌘K 跳到件详情" || note "  ✗ 深色下 ⌘K 没跳到件详情"
      shot 19f-item-stuck-dark
    fi
  fi
  open_popover || fails=$((fails+1)); sleep 1.8; shot 14-popover-dark
  popover_open && click status-item; sleep 0.6
  grep -E "feature|watch:|主线程|慢命令|sample|⌘K" "$OUT/app.log" | tail -40 | sed 's/^/    app: /' | tee -a "$HOW"
  note "真鼠标驱动完成，失败 $fails 处；最后状态：$(geo selection) · 卡片 $(geo cards) · 深色 $(geo dark)"
  [ $fails -le 6 ]   # 失败数也写在 HOW.txt，CI 绿不等于每一步都过
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
finder_icon_shot
sleep 1
stop_rec
pkill -x Evo 2>/dev/null || true
note "截图："; ls -1 "$OUT/shots" | sed 's/^/  /' | tee -a "$HOW"
[ "$(ls "$OUT/shots" | wc -l)" -gt 3 ] || { note "截图太少，算失败"; exit 1; }
