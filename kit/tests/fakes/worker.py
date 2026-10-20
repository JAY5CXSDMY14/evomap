#!/usr/bin/env python3
"""假工人：由假 Orca 在派工时同步启动，工作目录是本件工作区。
按 $FAKE_ORCA_DIR/plan.json 里的剧本依次出招（每个角色一个队列，用完默认 ok/pass）：
  build:  ok（在 scope 目录写文件并提交） | dirty（提交后再改一个已跟踪文件不提交） | fail（回报失败）
  verify: pass | fail
每次出招记一行到 workers.log：角色、任务号、招式、任务说明（JSON）。
"""
import fcntl, json, os, re, subprocess, sys

D = os.environ["FAKE_ORCA_DIR"]; role = sys.argv[1]
task, disp = os.environ["ORCA_TASK_ID"], os.environ["ORCA_DISPATCH_ID"]
spec = open(os.environ["ORCA_SPEC_FILE"], encoding="utf-8").read()
with open(os.path.join(D, "plan.lock"), "w") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    pf = os.path.join(D, "plan.json")
    plan = json.load(open(pf)) if os.path.exists(pf) else {}
    q = plan.get(role) or []
    move = q.pop(0) if q else ("ok" if role == "build" else "pass")
    plan[role] = q
    json.dump(plan, open(pf, "w"))
with open(os.path.join(D, "workers.log"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"role": role, "task": task, "move": move, "cwd": os.getcwd(), "spec": spec}, ensure_ascii=False) + "\n")

outcome = "succeeded"
if role == "build":
    if move == "fail":
        outcome = "failed"
    else:
        m = re.search(r"^scope: ([^,\n]+)", spec, re.M)
        d = (m.group(1).strip() if m else ".") or "."
        os.makedirs(d, exist_ok=True)
        fn = os.path.join(d, f"change-{task}.txt")
        open(fn, "w").write(f"{task}\n")
        subprocess.run(["git", "add", fn], check=True)
        subprocess.run(["git", "add", "-u"], check=True)      # 返工时把上一轮没提交的也收拾进来
        subprocess.run(["git", "commit", "-qm", f"feat: {task}"], check=True)
        if move == "dirty":
            open(fn, "a").write("没提交的改动\n")
else:
    outcome = "succeeded" if move == "pass" else "failed"
subprocess.run(["orca", "orchestration", "send", "--from", os.environ["ORCA_TERMINAL_HANDLE"], "--type", "worker_done",
                "--subject", f"{role} {outcome}", "--body", f"假{role}：{move}", "--task-id", task, "--dispatch-id", disp,
                "--outcome", outcome, "--json"], check=True, capture_output=True)
