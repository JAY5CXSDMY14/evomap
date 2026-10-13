#!/usr/bin/env bash
# 只合并审过的 sha。要求 PR 上已有包含该 sha 的 Review 评论（以 "Reviewed `<sha" 开头）。
#   scripts/merge-reviewed.sh <pr> <reviewed-sha>
set -euo pipefail
PR="${1:?usage: merge-reviewed.sh <pr> <reviewed-sha>}"; SHA="${2:?reviewed sha required}"
head=$(gh pr view "$PR" --json headRefOid -q .headRefOid)
[[ "$head" == "$SHA"* ]] || { echo "✗ PR head 已变为 ${head:0:8}，与审过的 ${SHA:0:8} 不同 → 重新 review" >&2; exit 1; }
short=${SHA:0:7}
gh pr view "$PR" --json comments,reviews -q '[.comments[].body, .reviews[].body][]' | grep -q "Reviewed \`$short" \
  || { echo "✗ 没有找到 \"Reviewed \`$short…\" 的 Review 评论。先写记录，再合并" >&2; exit 1; }
gh pr view "$PR" --json comments,reviews -q '[.comments[].body, .reviews[].body][]' | grep -q "Not run" \
  || echo "! Review 评论里没有 Not run 一行——如果确实全部跑了，写 'Not run: none'"
# squash 的提交信息必须自己写：默认信息会列出分支里所有 commit（含合进来的 main），
# 可能撑到几百 KB，把本 PR 自己的运行记录淹掉（magpie LESSONS 2026-10-13）。
subject=$(gh pr view "$PR" --json title,number -q '"\(.title) (#\(.number))"')
bodyf=$(mktemp); trap 'rm -f "$bodyf"' EXIT
gh pr view "$PR" --json body -q .body > "$bodyf"
printf '\nReviewed-at: %s\n' "$head" >> "$bodyf"
size=$(wc -c < "$bodyf")
(( size < 16384 )) || { echo "✗ 合并信息 ${size} 字节过大，精简 PR 描述后再合并" >&2; exit 1; }
gh pr merge "$PR" --squash --match-head-commit "$head" --delete-branch --subject "$subject" --body-file "$bodyf"
for n in $(gh pr view "$PR" --json closingIssuesReferences -q '.closingIssuesReferences[].number' 2>/dev/null); do
  gh issue edit "$n" --remove-label evo:in-progress --add-label evo:fixed-pending-confirm >/dev/null || true
done
echo "✓ merged #$PR at ${head:0:8}"
