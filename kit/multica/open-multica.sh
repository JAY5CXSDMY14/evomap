#!/bin/bash
# 可选：代理软件（Shadowrocket / Clash 的 fake-ip）把 *.ts.net 解析成 198.18.x 假地址时，用一个独立 Chrome 绕过。
# 用法：MULTICA_HOST=mac-mini.<tailnet>.ts.net MULTICA_IP=100.x.y.z bash open-multica.sh [/路径]
# MULTICA_IP 不填就用 `tailscale ip -4 <主机名前缀>` 去查。Chrome 会提示「不受支持的命令行标记」，忽略即可。
set -euo pipefail
HOST=${MULTICA_HOST:?请设置 MULTICA_HOST，例如 mac-mini.xxxx.ts.net}
PORT=${MULTICA_WEB_PORT:-8443}
IP=${MULTICA_IP:-$(tailscale ip -4 "${HOST%%.*}" 2>/dev/null | head -1)}
[ -n "$IP" ] || { echo "查不到 $HOST 的 tailnet IP，请设置 MULTICA_IP"; exit 1; }
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
exec "$CHROME" --user-data-dir="$HOME/.multica-chrome" --no-proxy-server \
  --host-resolver-rules="MAP $HOST $IP" --no-first-run --no-default-browser-check \
  "https://$HOST:$PORT${1:-/login}"
