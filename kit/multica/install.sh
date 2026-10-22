#!/bin/bash
# evo × Multica · 本机执行端安装（Air 先用，mini 接 TB 时同一份脚本）
#   bash install.sh                 只检查，不改任何东西
#   bash install.sh --apply         安装/更新：隔离 dsh（钉版本 + 自动补丁）、DSH_HOME、wrapper、启动脚本、LaunchAgent
#   bash install.sh --apply --from-tmp   另外把旧的 ~/tmp/dsh-home-multica 里 profiles/ 以外的文件（登录凭据、缓存等）拷过来：
#                                        新位置已有同名文件就跳过不覆盖；旧目录不删
#   Multica 的 dsh profile 包（multica-ai/dsh-multica-runtime）还没发到 npm（multica#6936）：脚本 clone + build + npm pack 成 tarball，
#   再用 `dsh plugin --profile multica add <tarball>` 装进 DSH_HOME（官方文档的做法），最后 `dsh --profile multica --probe` 验证：
#     默认源 = MULTICA_DSH_RUNTIME_PATH（已 clone/构建好的目录）> ~/.evoloop/multica/src/dsh-multica-runtime > 从 GitHub clone 到后者
#   bash install.sh --uninstall-agent    只卸 LaunchAgent（文件留着）
# 不碰：全局 dsh / DSH 桌面端、~/.dsh、evo 状态、Multica 服务端、sudo。可以反复跑。
# 服务端地址和登录（PAT）不在这里做：先 `multica login --token …`，本脚本只管 daemon 能起、能找到 dsh。
set -uo pipefail
KIT=$(cd "$(dirname "$0")" && pwd)
APPLY=0; FROMTMP=0; UNINST=0
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;; --from-tmp) FROMTMP=1 ;; --uninstall-agent) UNINST=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "不认识的参数：$a"; exit 2 ;;
  esac
done
ROOT=${EVO_MULTICA_DIR:-$HOME/.evoloop/multica}
DSHPKG=$ROOT/dsh; BIN=$ROOT/bin; DSHHOME=$ROOT/dsh-home; LOGS=$ROOT/logs
ENVF=$ROOT/env; START=$ROOT/start-daemon.sh
LABEL=com.evoloop.multica-daemon; PLIST=$HOME/Library/LaunchAgents/$LABEL.plist
ok(){ echo "  ✓ $1"; }; warn(){ echo "  ! $1"; }; info(){ echo "  · $1"; }; bad(){ echo "  ✗ $1"; HARD=1; }
HARD=0

if [ $UNINST = 1 ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null && ok "已卸 $LABEL" || info "$LABEL 没在跑"
  rm -f "$PLIST"; exit 0
fi

echo "== 1. Node 22+（daemon 会重置 PATH，dsh 的 #!/usr/bin/env node 会退回系统 Node 20，所以 wrapper 写死绝对路径）"
NODE=${EVO_NODE22:-}
if [ -z "$NODE" ]; then
  for c in "$BIN/node" /opt/homebrew/opt/node@22/bin/node /opt/homebrew/opt/node@24/bin/node /opt/homebrew/bin/node /usr/local/bin/node "$HOME/tmp/node22bin/node" "$(command -v node 2>/dev/null)"; do
    [ -n "$c" ] && [ -x "$c" ] || continue
    mj=$("$c" -p 'process.versions.node.split(".")[0]' 2>/dev/null) || continue
    [ "${mj:-0}" -ge 22 ] && { NODE=$(cd "$(dirname "$c")" && pwd -P)/$(basename "$c"); [ -L "$c" ] && NODE=$(readlink -f "$c" 2>/dev/null || python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$c"); break; }
  done
fi
if [ -n "$NODE" ]; then ok "Node: $NODE ($("$NODE" -v))"; else bad "找不到 Node 22+；装 brew install node@22，或设 EVO_NODE22=/绝对路径/node"; fi
NPM=$(dirname "$NODE")/npm; [ -x "$NPM" ] || NPM=$(command -v npm || true)

echo "== 2. 其他命令"
MULTICA=$(command -v multica || true)
[ -n "$MULTICA" ] && ok "multica: $MULTICA ($($MULTICA version 2>/dev/null | head -1))" || bad "没装 multica：brew install multica-ai/tap/multica"
CLAUDE=${MULTICA_CLAUDE_PATH:-$(command -v claude || true)}; [ -z "$CLAUDE" ] && [ -x "$HOME/.local/bin/claude" ] && CLAUDE=$HOME/.local/bin/claude
CODEX=${MULTICA_CODEX_PATH:-$(command -v codex || true)}; [ -z "$CODEX" ] && [ -x /Applications/ChatGPT.app/Contents/Resources/codex ] && CODEX=/Applications/ChatGPT.app/Contents/Resources/codex
[ -n "$CLAUDE" ] && ok "claude: $CLAUDE" || warn "没找到 claude（没有就不注册 Claude runtime）"
[ -n "$CODEX" ] && ok "codex: $CODEX" || warn "没找到 codex"
MAGKEY=${MAGPIE_GATEWAY_KEY:-}
if [ -z "$MAGKEY" ] && [ -f "$ENVF" ]; then MAGKEY=$(sed -n 's/^MAGPIE_GATEWAY_KEY=//p' "$ENVF" | tail -1); fi
[ -n "$MAGKEY" ] && ok "MAGPIE_GATEWAY_KEY 已有（不打印）" || bad "缺 MAGPIE_GATEWAY_KEY：第一次装请 MAGPIE_GATEWAY_KEY=… bash install.sh --apply"
curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:3425/v1/models -H "Authorization: Bearer ${MAGKEY}" | grep -q 200 && ok "Magpie 127.0.0.1:3425 通" || warn "Magpie 127.0.0.1:3425 不通或 key 不对"

RUNTIME_REPO=${MULTICA_DSH_RUNTIME_REPO:-https://github.com/multica-ai/dsh-multica-runtime}
RTSRC=${MULTICA_DSH_RUNTIME_PATH:-$ROOT/src/dsh-multica-runtime}
if [ -f "$RTSRC/package.json" ]; then ok "dsh-runtime 源码：$RTSRC"
elif [ -n "${MULTICA_DSH_RUNTIME_PATH:-}" ]; then bad "MULTICA_DSH_RUNTIME_PATH=$RTSRC 里没有 package.json"
else info "dsh-runtime 源码还没有，--apply 会 git clone $RUNTIME_REPO → $RTSRC"; command -v git >/dev/null || bad "没有 git"; fi

echo "== 3. 现状"
[ -x "$DSHPKG/node_modules/.bin/dsh" ] && ok "隔离 dsh 已装：$("$NODE" "$DSHPKG/node_modules/@deepseek-ai/dsh/lib/bin.js" --version 2>/dev/null | head -1)" || info "隔离 dsh 未装（--apply 会装）"
launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1 && ok "LaunchAgent $LABEL 在跑" || info "LaunchAgent 未加载"
pgrep -fl "multica daemon" >/dev/null 2>&1 && info "现在有 multica daemon 进程：$(pgrep -f 'multica daemon' | tr '\n' ' ')"

if [ $APPLY = 0 ]; then echo; [ $HARD = 0 ] && echo "检查完毕，可以 --apply。" || echo "有 ✗ 项，先处理。"; exit $HARD; fi
[ $HARD = 0 ] || { echo "有 ✗ 项，不装。"; exit 1; }

echo "== 4. 安装"
mkdir -p "$DSHPKG" "$BIN" "$DSHHOME/profiles/multica" "$LOGS"
ln -sf "$NODE" "$BIN/node"; ok "$BIN/node → $NODE（避开带空格的路径）"
export PATH="$BIN:$PATH"   # 之后 npm 的 #!/usr/bin/env node 也落到 Node 22
info "npm: $NPM（运行在 $(node -v)）"
# 4a. dsh-runtime：不在 npm 上 → 源码构建后打成 tarball（不用 file: 目录引用，免得源码目录被删就坏）
mkdir -p "$ROOT/vendor" "$(dirname "$RTSRC")"
if [ ! -f "$RTSRC/package.json" ]; then
  git clone --depth 1 "$RUNTIME_REPO" "$RTSRC" >"$LOGS/runtime-build.log" 2>&1 && ok "已 clone dsh-runtime" || { bad "clone 失败，看 $LOGS/runtime-build.log"; exit 1; }
fi
( cd "$RTSRC" && { [ -d node_modules ] || { [ -f package-lock.json ] && "$NPM" ci --no-audit --no-fund || "$NPM" install --no-audit --no-fund; }; } \
    && "$NPM" run build --if-present && rm -f "$ROOT"/vendor/*dsh-runtime*.tgz && "$NPM" pack --pack-destination "$ROOT/vendor" ) >>"$LOGS/runtime-build.log" 2>&1 \
  || { bad "dsh-runtime 构建/打包失败，看 $LOGS/runtime-build.log"; exit 1; }
RTTGZ=$(ls -t "$ROOT"/vendor/*dsh-runtime*.tgz 2>/dev/null | head -1)
[ -n "$RTTGZ" ] && ok "dsh-runtime tarball：$RTTGZ" || { bad "没找到 npm pack 产物"; exit 1; }
cp "$KIT/patch-dsh-boot.mjs" "$DSHPKG/"
cp "$KIT/package.json" "$DSHPKG/package.json"
( cd "$DSHPKG" && "$NPM" install --no-audit --no-fund >"$LOGS/npm-install.log" 2>&1 ) \
  && ok "npm install 完成（日志 logs/npm-install.log）" || { bad "npm install 失败，看 $LOGS/npm-install.log"; tail -5 "$LOGS/npm-install.log"; exit 1; }
"$NODE" "$DSHPKG/patch-dsh-boot.mjs" "$DSHPKG/node_modules/@deepseek-ai/dsh-app-boot/lib/index.js" || exit 1
HMRV=$("$NODE" -p 'require(process.argv[1]).version' "$DSHPKG/node_modules/@deepseek-ai/cordis-plugin-hmr/package.json" 2>/dev/null)
[ "$HMRV" = "1.0.17" ] && ok "cordis-plugin-hmr = 1.0.17" || { bad "cordis-plugin-hmr = ${HMRV:-?}，不是 1.0.17"; exit 1; }
grep -q registerConfig "$DSHPKG/node_modules/@deepseek-ai/cordis-plugin-hmr/lib/index.js" && ok "registerConfig 在" || { bad "registerConfig 不在"; exit 1; }

if [ $FROMTMP = 1 ] && [ -d "$HOME/tmp/dsh-home-multica" ]; then
  ( cd "$HOME/tmp/dsh-home-multica" && find . -type f ! -path './profiles/*' -print0 | while IFS= read -r -d '' f; do
      [ -e "$DSHHOME/$f" ] || { mkdir -p "$DSHHOME/$(dirname "$f")"; cp -p "$f" "$DSHHOME/$f"; echo "  · 拷 $f"; }; done )
  ok "旧 DSH_HOME 文件已拷（旧目录保留）"
fi
# 4b. 把 profile 包装进隔离 DSH_HOME（先装包，再放用户补丁层，免得被覆盖）
( export DSH_HOME="$DSHHOME" MAGPIE_GATEWAY_KEY="$MAGKEY"
  node "$DSHPKG/node_modules/@deepseek-ai/dsh/lib/bin.js" plugin --profile multica add "$RTTGZ" ) >"$LOGS/profile-add.log" 2>&1 \
  && ok "dsh profile multica 已装：$(basename "$RTTGZ")" || { bad "dsh plugin --profile multica add 失败，看 $LOGS/profile-add.log"; tail -5 "$LOGS/profile-add.log"; exit 1; }
cp "$KIT/cordis.patch.yml" "$DSHHOME/profiles/multica/cordis.patch.yml"; ok "用户补丁层 → dsh-home/profiles/multica/cordis.patch.yml"

cat > "$BIN/dsh" <<W
#!/bin/bash
# 由 kit/multica/install.sh 生成。Multica daemon 用这个 dsh：隔离的 0.1.0-rc.6 + Node 22 绝对路径。
exec "$BIN/node" "$DSHPKG/node_modules/@deepseek-ai/dsh/lib/bin.js" "\$@"
W
chmod +x "$BIN/dsh"; "$BIN/dsh" --version >/dev/null 2>&1 && ok "wrapper $BIN/dsh 能跑" || warn "wrapper 跑 --version 没成功，看一下"
if DSH_HOME="$DSHHOME" MAGPIE_GATEWAY_KEY="$MAGKEY" "$BIN/dsh" --profile multica --probe >"$LOGS/probe.log" 2>&1; then ok "dsh --profile multica --probe 通过（daemon 靠它注册 DSH）"
else bad "dsh --profile multica --probe 失败，看 $LOGS/probe.log"; tail -8 "$LOGS/probe.log"; exit 1; fi

umask 077
cat > "$ENVF" <<E
# 由 install.sh 生成，权限 600，不进 git。
DSH_HOME=$DSHHOME
MULTICA_DSH_PATH=$BIN/dsh
MULTICA_CLAUDE_PATH=$CLAUDE
MULTICA_CODEX_PATH=$CODEX
MAGPIE_GATEWAY_KEY=$MAGKEY
PATH=$BIN:$DSHPKG/node_modules/.bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
E
chmod 600 "$ENVF"; ok "环境变量 → $ENVF（600）"
umask 022
cat > "$START" <<'S'
#!/bin/bash
# 由 install.sh 生成：读 env 后前台跑 multica daemon（launchd 管它）。
D=$(cd "$(dirname "$0")" && pwd)
set -a; . "$D/env"; set +a
[ -z "${MULTICA_CLAUDE_PATH:-}" ] && unset MULTICA_CLAUDE_PATH
[ -z "${MULTICA_CODEX_PATH:-}" ] && unset MULTICA_CODEX_PATH
exec multica daemon start "$@"
S
sed -i '' "s#^exec multica#exec $MULTICA#" "$START" 2>/dev/null || sed -i "s#^exec multica#exec $MULTICA#" "$START"
chmod +x "$START"; ok "启动脚本 → $START"

mkdir -p "$(dirname "$PLIST")"
cat > "$PLIST" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$START</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$LOGS/daemon.out.log</string>
  <key>StandardErrorPath</key><string>$LOGS/daemon.err.log</string>
</dict></plist>
P
ok "LaunchAgent → $PLIST（环境变量在 env 文件里，不进 plist）"
echo
echo "装好了。接管前先停掉手动起的 daemon：multica daemon stop（或 kill 旧 pid），再："
echo "  launchctl bootstrap gui/\$(id -u) $PLIST"
echo "看日志：tail -f $LOGS/daemon.*.log ；查状态：multica daemon status ；multica runtime list"
