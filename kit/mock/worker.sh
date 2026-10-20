#!/bin/bash
# 假工人：读入 Orca 注入的派工说明，做一次小改动，回报 worker_done。只用于预演。
ROLE=${1:-build}; ORCA=${ORCA:-orca}
while IFS= read -r line; do
  [[ $line =~ --task-id\ ([a-z0-9_]+)\ --dispatch-id\ ([a-z0-9_]+) ]] && { T=${BASH_REMATCH[1]}; D=${BASH_REMATCH[2]}; }
  if [[ $line == *"=== TASK ==="* && -n $D ]]; then
    spec=""; while IFS= read -r -t 1 l; do spec+="$l"$'\n'; done
    $ORCA orchestration send --from "${ORCA_TERMINAL_HANDLE:-worker}" --type heartbeat --subject alive --task-id $T --dispatch-id $D --phase implementing --json >/dev/null
    out=succeeded
    if [[ $ROLE == build ]]; then
      f=$(echo "$spec" | grep -o 'scope: [^ ;]*' | head -1 | cut -d' ' -f2); f=${f:-.}
      mkdir -p "$f"; echo "change $T $(date +%s)" >> "$f/mock.txt"; git add "$f/mock.txt"; git commit -qm "mock($T)"
    else
      [[ -f FAIL_ONCE && ! -f .failed ]] && { touch .failed; out=failed; }
    fi
    $ORCA orchestration send --from "${ORCA_TERMINAL_HANDLE:-worker}" --type worker_done --subject "$ROLE $out" --body "$( [[ $ROLE == build ]] && printf '```json\n{"status":"done","summary":"mock %s","changes":[],"tests":[],"unfinished":[],"risks":[],"manual_checks":[]}\n```' "$T" || echo "mock $ROLE $out")" --task-id $T --dispatch-id $D --outcome $out --json >/dev/null
    T=; D=
  fi
done
