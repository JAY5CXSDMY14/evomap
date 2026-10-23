#!/usr/bin/env bash
# Red check：把非测试文件恢复到基线（默认 origin/main），只保留新测试，测试必须失败。
#   scripts/red-check.sh [--base <ref>] [--cmd "<test command>"] <test-file>...
# 退出码：0 = 测试在旧代码下失败（好）；1 = 测试在旧代码下通过（测试无效）；2 = 用法/环境错误
set -uo pipefail
BASE=origin/main; CMD="${EVO_TEST_CMD:-}"
while [ $# -gt 0 ]; do case "$1" in
  --base) BASE="$2"; shift 2;; --cmd) CMD="$2"; shift 2;; *) break;; esac; done
[ $# -gt 0 ] || { echo "usage: red-check.sh [--base ref] [--cmd cmd] <test-file>..." >&2; exit 2; }
[ -n "$CMD" ] || { echo "设置 EVO_TEST_CMD 或 --cmd，例如 --cmd 'pytest -x'（测试文件会追加到命令后）" >&2; exit 2; }
git diff --quiet && git diff --cached --quiet || { echo "工作区有未提交改动，先提交" >&2; exit 2; }

TESTS=("$@"); HEAD_SHA=$(git rev-parse HEAD); BASE_SHA=$(git rev-parse "$BASE")
mapfile -t CHANGED < <(git diff --name-only "$BASE_SHA" "$HEAD_SHA")
restore() { git checkout -q "$HEAD_SHA" -- . ; git clean -qfd >/dev/null 2>&1 || true; }
trap restore EXIT

echo "Red check: 非测试文件恢复到 $BASE ($(git rev-parse --short "$BASE_SHA"))，保留 ${TESTS[*]}"
for f in "${CHANGED[@]}"; do
  keep=0; for t in "${TESTS[@]}"; do [ "$f" = "$t" ] && keep=1; done
  [ $keep = 1 ] && continue
  if git cat-file -e "$BASE_SHA:$f" 2>/dev/null; then git checkout -q "$BASE_SHA" -- "$f"; else rm -f "$f"; fi
done

out=$(eval "$CMD ${TESTS[*]}" 2>&1); rc=$?
echo "$out" | tail -30
if [ $rc -eq 0 ]; then
  echo "✗ RED CHECK FAILED: 旧代码下测试通过，测试没有证明这次改动"; exit 1
fi
if echo "$out" | grep -qiE 'SyntaxError|ImportError|ModuleNotFoundError|cannot find|undefined:|build failed|no tests ran|collected 0 items|skipped'; then
  echo "! 失败看起来是编译/导入错误或被跳过——按标准这不算有效的 Red check，请检查失败信息是否指向错误行为"; exit 1
fi
echo "✓ RED CHECK OK: 旧代码下测试失败（rc=${rc}）。把上面的失败信息贴进 commit 的 Red: 行"; exit 0
