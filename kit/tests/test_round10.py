"""第十轮：决策岗的决定回流、施工提问有答复、pull 只交一次、先上线再标记、崩溃安全、
合并冲突自动返工、自动收菜、心跳看门狗、不做即清理、夜审补跑、防睡眠检查。"""
import json, os, subprocess, sys

from conftest import KIT, state_is

WORKER = os.path.join(KIT, "tests", "fakes", "worker.py")
K = "AB-FIX-001"


def with_decider(loop, **lim):
    loop.write_global({"roles": {"decide": {"cmd": f"{sys.executable} {WORKER} decide", "models": ["model-x"],
                                            "prompt": "roles/decider.md", "boot_seconds": 0}},
                       "limits": lim})


def decisions(*ds):
    return {"decisions": list(ds)}


def builds(loop):
    return [w for w in loop.workers() if w["role"] == "build"]


def escalate_by_verify_fail(loop, decide):
    """返工上限 0：验收一次不过就交决策岗；决策岗同一轮被叫醒并交出 decide 这份决定。"""
    with_decider(loop, rework_rounds=0)
    loop.project("AB")
    loop.plan(verify=["fail"], decide=[decide])
    loop.add("AB")
    loop.run_until("AB", state_is("escalated"))
    assert len([w for w in loop.workers() if w["role"] == "decide"]) == 1


# ---------- B1 决策岗的决定回流 ----------
def test_decider_retry_resumes_from_breakpoint(loop):
    with_decider(loop)
    repo = loop.project("AB")
    loop.plan(decide=[decisions({"item": K, "action": "retry", "note": "主目录已清理"})])
    loop.add("AB")
    loop.run_until("AB", state_is("verifying"))
    open(os.path.join(repo, "README.md"), "a").write("手改没提交\n")     # 主目录脏 → 合并受阻（带断点）
    loop.tick("AB")
    it = loop.item("AB")
    assert it["state"] == "escalated" and it["resume"] == "verified"
    loop.git(repo, "checkout", "README.md")
    st = loop.run_until("AB", state_is("merged"))
    assert any("决策岗：从断点继续" in l for l in st["log"])
    assert st["items"][K]["round"] == 0 and len(builds(loop)) == 1


def test_decider_rework_resets_round_and_carries_note(loop):
    escalate_by_verify_fail(loop, decisions({"item": K, "action": "rework", "note": "改成服务端校验"}))
    st = loop.run_until("AB", state_is("merged"))
    it = st["items"][K]
    assert it["round"] == 0 and it["decider_reworks"] == 1
    assert "决策岗：改成服务端校验" in builds(loop)[-1]["spec"]
    assert any("轮次清零" in l for l in st["log"])


def test_decider_drop_cleans_up(loop):
    escalate_by_verify_fail(loop, decisions({"item": K, "action": "drop", "note": "需求取消"}))
    wt = loop.item("AB")["worktree"]
    assert os.path.isdir(wt)
    loop.tick("AB")
    it = loop.item("AB")
    assert it["state"] == "dropped" and not os.path.isdir(wt)
    terms = loop.orca_state()["terminals"]
    assert all(not terms[d["terminal"]]["open"] for d in it["dispatch"].values())


def test_decider_split_drops_original_and_adds_children(loop):
    kids = [{"kind": "fix", "title": "修复注册页按钮", "scope": "web/a/"},
            {"kind": "ux", "title": "调整注册页提示文字", "scope": ["web/b/"], "look": True}]
    escalate_by_verify_fail(loop, decisions({"item": K, "action": "split", "note": "两件分开做", "items": kids}))
    loop.tick("AB")
    st = loop.state("AB")
    assert st["items"][K]["state"] == "dropped"
    a, b = st["items"]["AB-FIX-002"], st["items"]["AB-UX-001"]
    assert a["parent"] == K and b["parent"] == K and b["ui"] and b["scope"] == ["web/b/"]
    assert "两件分开做" in a["spec"]
    st = loop.run_until("AB", lambda s: s["items"]["AB-FIX-002"]["state"] == "merged", n=10)


def test_decider_split_with_bad_child_title_keeps_original(loop):
    kids = [{"kind": "fix", "title": "AB-FIX-9 修复v2草案", "scope": "web/"}]
    escalate_by_verify_fail(loop, decisions({"item": K, "action": "split", "items": kids}))
    loop.tick("AB")
    st = loop.state("AB")
    assert st["items"][K]["state"] == "escalated" and len(st["items"]) == 1
    assert any("子件不合规" in l for l in st["log"])


def test_decider_ask_owner_gate_then_answer_goes_back(loop):
    escalate_by_verify_fail(loop, decisions({"item": K, "action": "ask_owner", "note": "要不要清掉旧的验证码记录"}))
    loop.tick("AB")
    gates = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "ask"]
    assert len(gates) == 1 and gates[0]["item"] == K and gates[0]["options"] == ["同意", "不同意"]
    sent = [m for m in loop.telegram_sent() if "决策岗请你定" in m["text"]]
    assert len(sent) == 1 and "reply_markup" in sent[0]
    loop.ok("-p", "AB", "approve", gates[0]["id"], "不同意", "旧记录要留着")
    it = loop.item("AB")
    assert "老板答复" in it["ask"] and "旧记录要留着" in it["ask"]
    loop.env["EVO_NOW"] = "2026-10-20T12:31:00+08:00"
    loop.tick("AB")
    dec = [w for w in loop.workers() if w["role"] == "decide"]
    assert len(dec) == 2 and f"【新】{K}" in dec[1]["spec"] and "旧记录要留着" in dec[1]["spec"]
    assert len([m for m in loop.telegram_sent() if "决策岗请你定" in m["text"]]) == 1     # 5 分钟提醒不重复


def test_decider_without_json_leaves_items(loop):
    escalate_by_verify_fail(loop, "pass")                 # 默认招式：不交决定 JSON
    loop.tick("AB")
    st = loop.state("AB")
    assert st["items"][K]["state"] == "escalated"
    assert any("决策岗没交可用的决定" in l for l in st["log"])


# ---------- B2 施工提问有答复 ----------
def test_decider_answer_reaches_asking_builder(loop):
    with_decider(loop)
    loop.project("AB")
    loop.plan(build=["blocked"], decide=[decisions({"item": K, "action": "answer", "note": "用 Redis 存验证码"})])
    loop.add("AB")
    loop.run_until("AB", state_is("asking"))
    st = loop.run_until("AB", state_is("merged"), n=10)
    assert "决策岗答复：用 Redis 存验证码" in builds(loop)[1]["spec"]
    assert st["items"][K]["round"] == 0


# ---------- B3 pull 登记不了的只交一次 ----------
def issue(n, title, labels, author="boss"):
    return {"number": n, "title": title, "labels": [{"name": l} for l in labels], "author": {"login": author}, "body": ""}


def test_pull_flags_unregistrable_issue_once(loop):
    loop.project("AB", github_repo="o/r", trusted_authors=["boss"])
    p = os.path.join(loop.orca_dir, "gh_issues.json")
    json.dump([issue(5, "修复登录页报错", ["autopilot:ready", "type:fix"]),
               issue(6, "修复登录页报错v2草案", ["autopilot:ready", "type:fix", "scope:web/"])], open(p, "w"))
    loop.ok("-p", "AB", "pull"); loop.ok("-p", "AB", "pull")
    st = loop.state("AB")
    inbox = st["decide_inbox"]
    assert sorted(e["issue"] for e in inbox) == ["5", "6"] and not st["items"]
    assert "scope" in next(e for e in inbox if e["issue"] == "5")["note"]
    assert "标题不合规范" in next(e for e in inbox if e["issue"] == "6")["note"]
    json.dump([issue(5, "修复登录页报错", ["autopilot:ready", "type:fix", "scope:web/"])], open(p, "w"))
    loop.ok("-p", "AB", "pull")
    st = loop.state("AB")
    assert [it["issue"] for it in st["items"].values()] == ["5"] and len(st["decide_inbox"]) == 2


# ---------- B4 先上线，成功才标记 ----------
def ship_ready(loop, deploy):
    loop.project("AB", github_repo="o/r", trusted_authors=["boss"], deploy_cmd=deploy)
    loop.add("AB", extra=["--issue", "7"])
    loop.run_until("AB", state_is("merged"))
    loop.ok("-p", "AB", "ship")
    g = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]
    assert len(g) == 1
    loop.ok("-p", "AB", "approve", g[0]["id"], "上线")
    return loop.item("AB")


def test_ship_deploy_success_marks_shipped_and_closes_issue(loop):
    flag = os.path.join(loop.tmp, "DEPLOYED")
    it = ship_ready(loop, f"touch {flag}")
    assert os.path.exists(flag) and it["state"] == "shipped" and not it.get("ship_gate")
    gh = open(os.path.join(loop.orca_dir, "gh.log"), encoding="utf-8").read()
    assert "issue close 7" in gh and "已上线" in gh


def test_ship_deploy_failure_keeps_merged_and_pushes(loop):
    it = ship_ready(loop, "echo 部署炸了 >&2; false")
    assert it["state"] == "merged" and not it.get("ship_gate")
    assert any(e["kind"] == "deploy_failed" for e in loop.outbox())
    assert any("上线失败" in m["text"] and "部署炸了" in m["text"] for m in loop.telegram_sent())
    gh = open(os.path.join(loop.orca_dir, "gh.log"), encoding="utf-8").read()
    assert "issue close" not in gh
    loop.ok("-p", "AB", "ship")                               # 闸门清掉了：可以重新攒批
    assert [g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]


# ---------- B5 崩溃安全 ----------
def test_redelivered_messages_are_processed_once(loop):
    loop.env["FAKE_ORCA_NO_ACK"] = "1"
    loop.project("AB")
    loop.plan(verify=["fail"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"), n=12)
    it = st["items"][K]
    assert it["round"] == 1                                  # 重投的「验收不通过」没有多算一轮
    assert len(builds(loop)) == 2 and len([w for w in loop.workers() if w["role"] == "verify"]) == 2
    assert len(st["msg_seen"]) >= 4


def test_state_saved_right_after_dispatch(loop):
    loop.project("AB")
    loop.add("AB")
    loop.env["EVO_TEST_CRASH"] = "start_worker"
    r = loop.evo("-p", "AB", "tick")
    assert r.returncode == 3
    it = loop.item("AB")
    assert it["state"] == "building" and it["dispatch"]["build"]["id"]   # 派工已落盘
    loop.env.pop("EVO_TEST_CRASH")
    loop.run_until("AB", state_is("merged"))
    assert len(builds(loop)) == 1                              # 崩溃后没有重复派工


# ---------- C6 合并冲突 / 合并前测试红 → 自动返工 ----------
def test_red_premerge_tests_trigger_rework(loop):
    cnt = os.path.join(loop.tmp, "runs")
    loop.project("AB", test_cmd=f"n=$(cat {cnt} 2>/dev/null || echo 0); echo $((n+1)) > {cnt}; test $n -ge 1")
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"), n=10)
    assert st["items"][K]["round"] == 1
    spec = builds(loop)[1]["spec"]
    assert "合并前重跑测试不绿" in spec and "rebase" in spec


def test_rebase_conflict_triggers_rework_then_escalates(loop):
    repo = loop.project("AB")
    loop.add("AB")
    st = loop.run_until("AB", state_is("verifying"))
    wt = st["items"][K]["worktree"]
    mine = [f for f in loop.git(wt, "ls-files", "web").splitlines() if f.startswith("web/change-")][0]
    os.makedirs(os.path.join(repo, "web"), exist_ok=True)
    open(os.path.join(repo, mine), "w").write("主线上的另一个版本\n")
    loop.git(repo, "add", mine); loop.git(repo, "commit", "-qm", "主线改了同一个文件")
    loop.tick("AB")
    it = loop.item("AB")
    assert it["state"] in ("queued", "building") and it["round"] == 1
    assert "对齐主线冲突" in loop.orca_state()["tasks"][it["build"]]["spec"]
    st = loop.run_until("AB", state_is("escalated"), n=12)      # 施工一直不 rebase：超过上限才交决策岗
    assert st["items"][K]["round"] == 3


# ---------- C8 自动收菜 ----------
def test_auto_ship_gate_once_a_day_after_0820(loop):
    loop.write_global({"auto_ship_gate": True})
    loop.project("AB")
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"))             # 12:00 已过 08:20：合并那一轮就建闸门
    g = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]
    assert len(g) == 1 and st["auto_ship_day"] == "2026-10-20"
    loop.ok("-p", "AB", "approve", g[0]["id"], "再等等")
    loop.tick("AB")
    assert not [g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]   # 当天不再建
    loop.env["EVO_NOW"] = "2026-10-21T08:00:00+08:00"
    loop.tick("AB")
    assert not [g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]
    loop.env["EVO_NOW"] = "2026-10-21T08:25:00+08:00"
    loop.tick("AB")
    assert len([g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]) == 1
    loop.tick("AB")
    assert len([g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]) == 1


def test_auto_ship_skips_when_main_red(loop):
    red = os.path.join(loop.tmp, "RED")
    loop.project("AB", test_cmd=f"test ! -f {red}")
    loop.add("AB")
    loop.run_until("AB", state_is("merged"))                  # 自动收菜默认关着先合并
    open(red, "w").close()
    loop.write_global({"auto_ship_gate": True})
    loop.tick("AB")
    assert not [g for g in loop.status_json("AB")["gates"] if g["kind"] == "ship"]
    assert any(e["kind"] == "main_red" for e in loop.outbox())


# ---------- D10 心跳与看门狗 ----------
def test_heartbeat_status_and_watchdog(loop):
    loop.project("AB")
    loop.tick("AB")
    hb = json.load(open(os.path.join(loop.root, "heartbeat.json")))
    assert hb == {"AB": "2026-10-20T12:00:00+08:00"}
    s = loop.status_json("AB")
    assert s["last_tick"] == "2026-10-20T12:00:00+08:00" and s["schema_version"] == 1
    stalled = lambda: [m for m in loop.telegram_sent() if "接棒器停了" in m["text"]]
    loop.env["EVO_NOW"] = "2026-10-20T12:09:00+08:00"
    loop.ok("watchdog")
    assert stalled() == []
    loop.env["EVO_NOW"] = "2026-10-20T12:11:00+08:00"
    loop.ok("watchdog"); loop.ok("watchdog")
    assert len(stalled()) == 1 and "[AB]" in stalled()[0]["text"]
    loop.tick("AB")                                           # 恢复转动
    loop.ok("watchdog")
    assert any(e["kind"] == "watchdog_recovered" for e in loop.outbox())
    loop.env["EVO_NOW"] = "2026-10-20T12:30:00+08:00"
    loop.ok("watchdog")
    assert len(stalled()) == 2                                # 恢复后再停：再推一次


def test_watchdog_threshold_configurable_and_bot_runs_it(loop):
    loop.write_global({"limits": {"heartbeat_stale_minutes": 30}})
    loop.project("AB")
    loop.tick("AB")
    loop.env["EVO_NOW"] = "2026-10-20T12:20:00+08:00"
    loop.ok("watchdog")
    assert not any(e["kind"] == "stalled" for e in loop.outbox())
    loop.env["EVO_NOW"] = "2026-10-20T12:31:00+08:00"
    loop.ok("bot", "--once")
    assert any(e["kind"] == "stalled" and e["project"] == "AB" for e in loop.outbox())


# ---------- C9 不做即清理 ----------
def test_product_no_drops_and_unblocks_next_item(loop):
    loop.project("AB")
    loop.add("AB", "新增注册页邀请码", "web/", ["--product"])
    loop.add("AB", "修复注册页提示文字", "web/login")
    gate = loop.status_json("AB")["gates"][0]["id"]
    loop.ok("-p", "AB", "approve", gate, "不做")
    st = loop.state("AB")
    assert st["items"]["AB-FIX-001"]["state"] == "dropped"
    st = loop.run_until("AB", lambda s: s["items"]["AB-FIX-002"]["state"] == "merged", n=10)
    assert any("AB-FIX-001 不做" in l for l in st["log"])


# ---------- D11 夜审补跑 ----------
def set_state(loop, **kv):
    p = os.path.join(loop.projects, "AB", "state", "state.json")
    s = json.load(open(p, encoding="utf-8")); s.update(kv)
    json.dump(s, open(p, "w", encoding="utf-8"), ensure_ascii=False)


def test_nightly_runs_after_time_and_catches_up_yesterday(loop):
    loop.project("AB")
    loop.tick("AB")
    loop.ok("-p", "AB", "once")                               # 12:00：没到点，什么都不做
    assert "nightly_done" not in loop.state("AB")
    loop.env["EVO_NOW"] = "2026-10-20T23:40:00+08:00"
    loop.ok("-p", "AB", "once")
    assert loop.state("AB")["nightly_done"] == "2026-10-20"
    # 机器 10-19 晚上关着：10-20 早上开机先补跑 10-19
    set_state(loop, nightly_done="2026-10-18", log=["10-19 15:00 AB-FIX-009 第 1 轮返工：按钮错位"])
    loop.env["EVO_NOW"] = "2026-10-20T07:00:00+08:00"
    loop.ok("-p", "AB", "once")
    st = loop.state("AB")
    assert st["nightly_done"] == "2026-10-19"
    assert [it["title"] for it in st["items"].values()] == ["更新 10-19 错题本"]
    assert any("补跑 10-19 的夜审" in l for l in st["log"])
    loop.env["EVO_NOW"] = "2026-10-20T09:00:00+08:00"
    loop.ok("-p", "AB", "once")
    st = loop.state("AB")
    assert st["nightly_done"] == "2026-10-19" and len(st["items"]) == 1


def test_nightly_no_catch_up_after_noon_or_for_new_project(loop):
    loop.project("AB")
    loop.env["EVO_NOW"] = "2026-10-20T07:00:00+08:00"
    loop.ok("-p", "AB", "once")
    assert "nightly_done" not in loop.state("AB")             # 新项目不补
    set_state(loop, nightly_done="2026-10-18")
    loop.env["EVO_NOW"] = "2026-10-20T13:00:00+08:00"
    loop.ok("-p", "AB", "once")
    assert loop.state("AB")["nightly_done"] == "2026-10-18"   # 过了中午不补，等今晚


# ---------- D11 install.sh 防睡眠检查 ----------
def test_install_warns_when_mac_sleeps(loop):
    fake = os.path.join(loop.tmp, "fakebin"); os.makedirs(fake)
    for name, text in (("uname", "echo Darwin"), ("pmset", "printf ' sleep                1\\n disksleep            10\\n'")):
        p = os.path.join(fake, name); open(p, "w").write("#!/bin/bash\n" + text + "\n"); os.chmod(p, 0o755)
    env = {**loop.env, "PATH": fake + os.pathsep + loop.env["PATH"]}
    r = subprocess.run(["bash", os.path.join(KIT, "install.sh")], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "sudo pmset -a sleep 0 disksleep 0" in r.stdout and "会睡眠" in r.stdout
    open(os.path.join(fake, "pmset"), "w").write("#!/bin/bash\nprintf ' sleep 0\\n disksleep 0\\n'\n")
    r = subprocess.run(["bash", os.path.join(KIT, "install.sh")], env=env, capture_output=True, text=True)
    assert "防睡眠已设置" in r.stdout and "sudo pmset" not in r.stdout
