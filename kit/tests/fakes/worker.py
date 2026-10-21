#!/usr/bin/env python3
"""假工人：由假 Orca 在派工时同步启动，工作目录是本件工作区。
按 $FAKE_ORCA_DIR/plan.json 里的剧本依次出招（每个角色一个队列，用完默认 ok/pass）：
  build:  ok（在 scope 目录写文件并提交，按格式交卷） | dep:<包名>（另在 scope 目录 package.json 加依赖） | file:<路径> | dirty（提交后再改一个已跟踪文件不提交） | fail（回报失败）
          noreport（不交 JSON） | oos（另外改了范围外的文件） | blocked / unfinished / redtest（交卷内容不合格）
  verify: pass | fail
          same（不改任何东西，照常交卷：返工后指纹不变）
  任何角色：ratelimit（打印额度提示并回报失败）| ratelimit-hang（打印提示后不回报）| silent（不回报）
          die（工人进程死掉：不回报，worker-show 报这次派工 exited）
  decide（决策岗）：默认 pass（不交决定 JSON）；剧本项写成对象 {"decisions": [...]} 就原样放进 ```json 块交卷
  FAKE_ORCA_NO_ACK=1 时假 Orca 不认确认，消息每轮重投（测去重）
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
RL = os.environ.get("FAKE_RL_TEXT", "Claude usage limit reached. Your limit will reset at 5pm (Asia/Shanghai).")
if isinstance(move, dict):               # 决策岗交决定：剧本里直接写 {"decisions": [...]}
    body = "假决策岗\n```json\n" + json.dumps(move, ensure_ascii=False) + "\n```"
    subprocess.run(["orca", "orchestration", "send", "--from", os.environ["ORCA_TERMINAL_HANDLE"], "--type", "worker_done",
                    "--subject", f"{role} succeeded", "--body", body, "--task-id", task, "--dispatch-id", disp,
                    "--outcome", "succeeded", "--json"], check=True, capture_output=True)
    sys.exit(0)
if move == "ratelimit":                  # 额度用完：打印提示，回报失败
    print("working...\n" + RL); outcome = "failed"
elif move == "ratelimit-hang":           # 额度用完：打印提示后不回报（停在提示上）
    print("working...\n" + RL); sys.exit(0)
elif move == "silent":                   # 什么都不回报（模拟卡住）
    sys.exit(0)
elif move == "die":                      # 工人进程死掉：不回报，假 Orca 的 worker-show 对这次派工报「不在了」
    open(os.path.join(D, "dead.txt"), "a").write(disp + "\n"); sys.exit(0)
elif role == "build" and move == "same":  # 返工时什么都不改（改动指纹不变），照常按格式交卷
    pass
elif role == "build":
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
        if move == "oos":
            open("outside-scope.txt", "w").write("越界\n")
            subprocess.run(["git", "add", "outside-scope.txt"], check=True)
            subprocess.run(["git", "commit", "-qm", "chore: 顺手改别处"], check=True)
        if move == "dirty":
            open(fn, "a").write("没提交的改动\n")
        if isinstance(move, str) and move.startswith(("dep:", "file:")):   # dep:<包名> 往 scope 目录的 package.json 加依赖；file:<路径> 新建文件
            kind, _, arg = move.partition(":")
            if kind == "dep":
                pj = os.path.join(d, "package.json")
                j = json.load(open(pj)) if os.path.exists(pj) else {"name": "web", "dependencies": {}}
                j.setdefault("dependencies", {})[arg] = "^1.0.0"
                json.dump(j, open(pj, "w"), indent=2); target = pj
            else:
                target = arg; os.makedirs(os.path.dirname(arg) or ".", exist_ok=True); open(arg, "w").write("export {}\n")
            subprocess.run(["git", "add", target], check=True)
            subprocess.run(["git", "commit", "-qm", f"feat: {move}"], check=True)
else:
    outcome = "succeeded" if move == "pass" else "failed"
body = f"假{role}：{move}"
if role == "build" and outcome == "succeeded" and move != "noreport":
    rep = {"status": {"blocked": "blocked", "unfinished": "in_progress"}.get(move, "done"), "summary": f"假施工 {task}",
           "changes": [{"path": "web/", "why": "测试"}],
           "tests": [{"command": "make test", "result": "failed" if move == "redtest" else "passed"}],
           "unfinished": ["还差一半"] if move in ("unfinished", "blocked") else [], "risks": [],
           "manual_checks": ["在 1280px 宽度下看注册页"]}
    body += "\n```json\n" + json.dumps(rep, ensure_ascii=False) + "\n```"
subprocess.run(["orca", "orchestration", "send", "--from", os.environ["ORCA_TERMINAL_HANDLE"], "--type", "worker_done",
                "--subject", f"{role} {outcome}", "--body", body, "--task-id", task, "--dispatch-id", disp,
                "--outcome", outcome, "--json"], check=True, capture_output=True)
