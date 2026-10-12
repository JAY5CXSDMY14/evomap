#!/usr/bin/env bash
# 收集夜审上下文，输出 Markdown 到 stdout。
#   scripts/retro-collect.sh --since "<git date or sha>" [--until <ref>]
set -euo pipefail
SINCE=""; UNTIL="origin/main"
while [ $# -gt 0 ]; do case "$1" in --since) SINCE="$2"; shift 2;; --until) UNTIL="$2"; shift 2;; *) shift;; esac; done
[ -n "$SINCE" ] || { last=$(git log "$UNTIL" --format=%H --grep='^lessons:' -1 || true); SINCE="${last:-24 hours ago}"; }
git fetch -q origin 2>/dev/null || true
if git rev-parse -q --verify "$SINCE^{commit}" >/dev/null; then RANGE="$SINCE..$UNTIL"; LOGARGS=("$RANGE")
else RANGE="since $SINCE"; LOGARGS=("$UNTIL" "--since=$SINCE"); fi
has_gh=0; command -v gh >/dev/null && gh auth status >/dev/null 2>&1 && has_gh=1
iso_since=$(git log "${LOGARGS[@]}" --reverse --format=%cI | sed -n 1p)

echo "# Retro context ($RANGE)"
echo
echo "- commits: $(git rev-list --count "${LOGARGS[@]}")"
echo "- tags in window: $(git tag --contains "$(git log "${LOGARGS[@]}" --reverse --format=%H | sed -n 1p)" 2>/dev/null | tr '\n' ' ')"
echo
echo "## Hotspots (files changed ≥3 times)"
git log "${LOGARGS[@]}" --name-only --format= | grep -v '^$' | sort | uniq -c | sort -rn | awk '$1>=3' | sed -n 1,20p
echo
echo "## Reverts / fix-of-fix candidates"
git log "${LOGARGS[@]}" --format='%h %s' | grep -iE 'revert|again|still|regress|返工|又|再次|follow-?up' || echo "(none by keyword)"
echo
echo "## Issues referenced by more than one commit"
git log "${LOGARGS[@]}" --format=%s | grep -oE '#[0-9]+' | sort | uniq -c | awk '$1>1' | sort -rn || true
echo
if [ $has_gh = 1 ] && [ -n "$iso_since" ]; then
  echo "## Merged PRs with review comments"
  gh pr list --state merged --search "merged:>=${iso_since%%T*}" --limit 100 --json number,title,mergeCommit \
    -q '.[]|"- #\(.number) \(.title) → \(.mergeCommit.oid[0:8])"'
  echo
  echo "## Regressed / reopened issues"
  gh issue list --label evo:regressed --state all --limit 50 --json number,title -q '.[]|"- #\(.number) \(.title)"'
  echo
  echo "## CI runs not successful"
  gh run list --limit 100 --json headSha,name,conclusion,createdAt \
    -q ".[]|select(.createdAt>=\"$iso_since\")|select(.conclusion!=\"success\")|\"- \(.headSha[0:8]) \(.name): \(.conclusion)\""
  echo
fi
echo "## Commits (full messages)"
git log "${LOGARGS[@]}" --reverse --format='### %h %ad%n%s%n%n%b%n---' --date=format:'%m-%d %H:%M'
