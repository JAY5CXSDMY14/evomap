#!/bin/bash
# evo 看门狗（第十八轮，自维护）。独立于 evo 本体：不属于任何功能包，自升级不碰它（装在 ~/.evoloop/guard/，不在 releases/ 里）。
# 施工任务书禁止修改本文件和回退逻辑（kit/selfmaint/），交卷改到这里一律打回；只有老板手改。
#
# launchd 每 60 秒跑一次（com.evoloop.guard）。只在「刚升级完的 10 分钟观察期」里动手：
#   upgrade.json 的 state = switched 且还在观察期，并且满足任一条：
#     1) evo selfcheck（新版本）失败
#     2) 切换已超过 GUARD_MINUTES（默认 10）分钟，runner.json 的心跳还停在切换之前（新版本没转起来）
#   → 把 ~/.evoloop/current 切回 releases/PREVIOUS 记的上一版，重启常驻进程，upgrade.json 记 rolled_back，推送一条。
# 观察期过了且心跳正常 → upgrade.json 记 ok，之后不再管。
# 用法：evo-guard.sh [--once]（同上，跑一次就退）；EVO_DIR 可改目录（测试用）；GUARD_NOW 可固定现在的 epoch 秒（测试用）。
set -uo pipefail
EVO_DIR=${EVO_DIR:-$HOME/.evoloop}
MIN=${GUARD_MINUTES:-10}
UP=$EVO_DIR/upgrade.json
CUR=$EVO_DIR/current
PREVF=$EVO_DIR/releases/PREVIOUS
LOG=$EVO_DIR/logs/guard.log
PY=${PYTHON:-$(command -v python3)}
now(){ if [ -n "${GUARD_NOW:-}" ]; then echo "$GUARD_NOW"; else date +%s; fi; }
say(){ mkdir -p "$(dirname "$LOG")"; echo "$(date '+%m-%d %H:%M:%S') $*" >> "$LOG"; echo "$*"; }
jget(){ "$PY" -c 'import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: d={}
v=d.get(sys.argv[2]); print("" if v is None else v)' "$1" "$2"; }

[ -f "$UP" ] || exit 0
STATE=$(jget "$UP" state)
[ "$STATE" = switched ] || exit 0
AT=$(jget "$UP" at); AT=${AT%.*}
TO=$(jget "$UP" to); FROM=$(jget "$UP" from)
NOW=$(now)
AGE=$(( NOW - ${AT:-$NOW} ))

why=""
if ! "$PY" "$CUR/bin/evo" selfcheck --json > "$EVO_DIR/guard-selfcheck.json" 2>&1; then
  why="新版本 $TO 自检失败"
elif [ "$AGE" -ge $(( MIN * 60 )) ]; then
  HB=$(jget "$EVO_DIR/runner.json" at); HB=${HB%.*}
  if [ -z "$HB" ] || [ "$HB" -lt "${AT:-0}" ]; then
    why="切到 $TO 已 $(( AGE / 60 )) 分钟，常驻进程没有心跳"
  else
    "$PY" - "$UP" <<'PYEOF'
import json, sys
p = sys.argv[1]; d = json.load(open(p)); d["state"] = "ok"; json.dump(d, open(p, "w"), ensure_ascii=False)
PYEOF
    say "观察期结束：$TO 正常"
    exit 0
  fi
fi
[ -z "$why" ] && exit 0

PREV=$(cat "$PREVF" 2>/dev/null)
if [ -z "$PREV" ] || [ ! -f "$EVO_DIR/releases/$PREV/bin/evo" ]; then
  say "要回退但找不到上一版（PREVIOUS=$PREV）：$why"
  MSG="evo 自升级出问题且没法回退：$why（找不到上一版），请手动处理"
else
  # 原子地换软链（mv 到一个指向目录的软链上会挪进目录里，所以用 os.replace）
  "$PY" -c 'import os,sys; t=sys.argv[1]+".guard"; os.path.lexists(t) and os.remove(t); os.symlink(sys.argv[2], t); os.replace(t, sys.argv[1])' "$CUR" "releases/$PREV"
  "$PY" - "$UP" "$why" <<'PYEOF'
import json, sys, time
p = sys.argv[1]; d = json.load(open(p)); d.update(state="rolled_back", why=sys.argv[2], rolled_back_at=time.time())
json.dump(d, open(p, "w"), ensure_ascii=False)
PYEOF
  say "已回退到 $PREV：$why"
  MSG="evo 自升级到 $TO 失败（$why），看门狗已切回上一版 $PREV"
  if [ "$(uname)" = Darwin ]; then
    launchctl kickstart -k "gui/$(id -u)/com.evoloop.autopilot" >/dev/null 2>&1 || true
  fi
fi
# 推送：outbox 一行（App / 外部 Agent 都读它）+ 有 Telegram 就发 + 本机通知
"$PY" - "$EVO_DIR/outbox.jsonl" "$MSG" <<'PYEOF'
import json, sys, time, uuid
ev = {"schema_version": 1, "id": uuid.uuid4().hex[:16], "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "epoch": round(time.time(), 3),
      "project": "*", "kind": "self_upgrade_rollback", "level": "push", "title": "自升级回退", "body": sys.argv[2],
      "item": None, "gate": None, "data": {"by": "evo-guard"}}
open(sys.argv[1], "a", encoding="utf-8").write(json.dumps(ev, ensure_ascii=False) + "\n")
PYEOF
if [ -n "${EVO_TG_TOKEN:-}" ] && [ -n "${EVO_TG_CHAT:-}" ] && [ -z "${GUARD_NO_NET:-}" ]; then
  curl -s -m 15 "${EVO_TG_API:-https://api.telegram.org}/bot$EVO_TG_TOKEN/sendMessage" \
       --data-urlencode "chat_id=$EVO_TG_CHAT" --data-urlencode "text=$MSG" >/dev/null 2>&1 || true
fi
if [ "$(uname)" = Darwin ] && [ -z "${GUARD_NO_NET:-}" ]; then
  osascript -e "display notification \"$MSG\" with title \"evo 看门狗\"" >/dev/null 2>&1 || true
fi
exit 0
