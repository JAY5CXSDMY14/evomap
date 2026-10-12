#!/usr/bin/env bash
# 认领 Issue 并建立独立 worktree。需要 gh（已登录）。
#   scripts/claim.sh <issue>          认领
#   scripts/claim.sh --setup-labels   创建 evoloop 标签
set -euo pipefail
STALE_HOURS="${EVO_CLAIM_STALE_HOURS:-2}"

if [ "${1:-}" = "--setup-labels" ]; then
  while IFS='|' read -r name color desc; do
    gh label create "$name" --color "$color" --description "$desc" --force >/dev/null && echo "label $name"
  done <<'L'
evo:ready|0e8a16|分诊通过，可认领
evo:needs-info|fbca04|缺复现或原始数据
evo:needs-human|d93f0b|需要维护者决定
evo:wontfix|cccccc|不符合方向
evo:duplicate|cccccc|重复
evo:in-progress|1d76db|已被某个会话认领
evo:needs-review|5319e7|等待 Reviewer
evo:changes-requested|e99695|Review 要求修改
evo:fixed-pending-confirm|c2e0c6|已合并，等报告人确认
evo:regressed|b60205|报告人确认没修好（夜审头号线索）
evo:retro|bfdadc|夜审复盘 PR
L
  exit 0
fi

ISSUE="${1:?usage: claim.sh <issue-number>}"
SESSION="${EVO_SESSION:-$(whoami)@$(hostname -s)-$$}"
git fetch -q origin

labels=$(gh issue view "$ISSUE" --json labels -q '.labels[].name')
grep -qx 'evo:ready' <<<"$labels" || { echo "✗ #$ISSUE 没有 evo:ready 标签，先分诊" >&2; exit 1; }

if grep -qx 'evo:in-progress' <<<"$labels"; then
  last=$(gh issue view "$ISSUE" --json comments -q '[.comments[]|select(.body|startswith("🔧 claimed"))][-1].createdAt')
  if [ -n "$last" ]; then
    age=$(( ( $(date +%s) - $(date -d "$last" +%s) ) / 3600 ))
    if [ "$age" -lt "$STALE_HOURS" ]; then
      echo "✗ #$ISSUE 已在 ${age}h 前被认领，未超过 ${STALE_HOURS}h，停止" >&2; exit 1
    fi
    echo "! 认领已超过 ${STALE_HOURS}h，视为放弃，重新认领"
  fi
fi

hits=$(git log origin/main --since="3 days ago" --format='%h %s' | grep -E "#${ISSUE}([^0-9]|$)" || true)
[ -n "$hits" ] && { echo "! origin/main 上已有提到 #$ISSUE 的 commit："; echo "$hits"; echo "  确认不是重复修复后再继续（Ctrl-C 退出，回车继续）"; read -r _; }
prs=$(gh pr list --state open --search "#$ISSUE" --json number,title -q '.[]|"#\(.number) \(.title)"')
[ -n "$prs" ] && { echo "✗ 已有 open PR 处理 #$ISSUE："; echo "$prs"; exit 1; }

title=$(gh issue view "$ISSUE" --json title -q .title)
slug=$(echo "$title" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g;s/^-|-$//g' | cut -c1-30)
branch="evo/${ISSUE}-${slug:-task}"
wt="../wt-${ISSUE}"

gh issue comment "$ISSUE" --body "🔧 claimed by \`$SESSION\` at $(date -u +%FT%TZ) · branch \`$branch\`" >/dev/null
gh issue edit "$ISSUE" --add-label evo:in-progress >/dev/null
git worktree add -q "$wt" -b "$branch" origin/main
echo "✓ #$ISSUE claimed → $wt ($branch)"
