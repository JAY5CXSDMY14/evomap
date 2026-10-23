#!/usr/bin/env bash
# CI 全绿（cancelled 不算）且满足攒批间隔才允许发版。
#   scripts/release-gate.sh <sha> [--p0]
set -euo pipefail
SHA="${1:?usage: release-gate.sh <sha> [--p0]}"; P0="${2:-}"
MIN_MIN="${EVO_MIN_RELEASE_MINUTES:-120}"
runs=$(gh run list --commit "$SHA" --json status,conclusion,name -q '.[]|"\(.name)|\(.status)|\(.conclusion)"')
[ -n "$runs" ] || { echo "✗ $SHA 没有任何 CI run" >&2; exit 1; }
bad=0
while IFS='|' read -r name status concl; do
  if [ "$status" != "completed" ]; then echo "✗ $name 未完成 ($status)"; bad=1
  elif [ "$concl" != "success" ] && [ "$concl" != "skipped" ]; then echo "✗ $name = ${concl}（cancelled 也不算通过）"; bad=1
  else echo "✓ $name"; fi
done <<<"$runs"
[ $bad = 0 ] || exit 1
last=$(git for-each-ref --sort=-creatordate --format='%(creatordate:unix)' refs/tags | sed -n 1p)
if [ -n "$last" ] && [ "$P0" != "--p0" ]; then
  gap=$(( ( $(date +%s) - last ) / 60 ))
  [ $gap -ge "$MIN_MIN" ] || { echo "✗ 距上次发布 ${gap} 分钟 < ${MIN_MIN}，攒批等待（P0 用 --p0）"; exit 1; }
fi
echo "✓ release gate passed for ${SHA:0:8}"
