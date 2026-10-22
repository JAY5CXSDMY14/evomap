"""第二十二轮：吸收《Context 与 Loop》第 1–6、14 条。

1 永久运行记录 runs/<件号>/；2+14 金丝雀件（判据先喂应该变红的输入，跳过绝不算通过）；
4 施工任务书开头固定角色声明、施工拿不到决策岗规则；6 推送成没成问远端。
（3 注入上限在 test_round22_sizes.py，5 错题本关单标准在 test_round22_lessons.py）
"""
import json, os, shutil, subprocess, sys

from conftest import KIT, EVO, state_is

sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_exec  # noqa: E402

WORKER = os.path.join(KIT, "tests", "fakes", "worker.py")
K = "AB-FIX-001"
DECL = "【角色】你是执行者，只做本任务，不要再派活、不要拆分给其他 agent。"
DECIDER_MARKS = ("# 决策岗", "动作只有这七个", '{"decisions"', "新 issue 分拣")


def runs_dir(loop, code="AB", key=K):
    return os.path.join(loop.projects, code, "runs", key)


def runs_index(loop, code="AB", key=K):
    p = os.path.join(runs_dir(loop, code, key), "index.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def with_decider(loop, **lim):
    loop.write_global({"roles": {"decide": {"cmd": f"{sys.executable} {WORKER} decide", "models": ["model-x"],
                                            "prompt": "roles/decider.md", "boot_seconds": 0}},
                       "limits": {"rework_rounds": 0, "decide_every_minutes": 0, **lim}})


# ---------- 1 永久运行记录 ----------
def test_run_trail_keeps_task_books_reports_premerge_and_push(loop):
    loop.project("AB")
    loop.add("AB")
    loop.run_until("AB", state_is("merged"), n=10)
    it = loop.item("AB")
    assert it["worktree"] is None or not os.path.isdir(it["worktree"])          # 合并后工作区收拾掉了……
    kinds = [r["kind"] for r in runs_index(loop)]                                 # ……运行记录还在
    for k in ("build-task-r0", "build-r0", "verify-task-r0", "verify-r0", "premerge-test", "push"):
        assert k in kinds, kinds
    d = runs_dir(loop)
    for r in runs_index(loop):
        for f in r["files"]:
            assert os.path.isfile(os.path.join(d, f)), f
    rep = next(r for r in runs_index(loop) if r["kind"] == "build-r0")
    body = open(os.path.join(d, rep["files"][0]), encoding="utf-8").read()
    assert '"status": "done"' in body and rep["outcome"] == "succeeded" and rep["role"] == "build"
    task = next(r for r in runs_index(loop) if r["kind"] == "build-task-r0")
    assert open(os.path.join(d, task["files"][0]), encoding="utf-8").read().startswith(DECL)
    push = next(r for r in runs_index(loop) if r["kind"] == "push")
    assert push["sha"] == loop.remote_head("AB") == push["remote_sha"]
    out = loop.ok("-p", "AB", "runs").stdout
    assert K in out
    j = json.loads(loop.ok("-p", "AB", "runs", K, "--json").stdout)
    assert j["schema_version"] == 1 and j["key"] == K and len(j["records"]) == len(runs_index(loop))
    assert loop.evo("-p", "AB", "runs", "AB-FIX-999").returncode != 0


def test_run_trail_survives_drop_and_rework(loop):
    loop.project("AB")
    loop.plan(verify=["fail"])
    loop.add("AB")
    loop.run_until("AB", lambda s: s["items"][K]["round"] >= 1, n=8)
    n = len(runs_index(loop))
    assert any(r["kind"] == "verify-r0" and r["outcome"] == "failed" for r in runs_index(loop))
    loop.ok("-p", "AB", "drop", K, "不做了")
    assert loop.item("AB")["state"] == "dropped"
    assert len(runs_index(loop)) >= n                                             # 不做也不删
    for _ in range(2):
        loop.tick("AB")
    assert os.path.isdir(runs_dir(loop))


def test_decider_batch_and_decisions_archived(loop):
    with_decider(loop)
    loop.project("AB")
    loop.plan(verify=["fail"], decide=[{"decisions": [{"item": K, "action": "drop", "note": "方向不对，不做"}]}])
    loop.add("AB")
    loop.run_until("AB", state_is("dropped"), n=10)
    dk = [r["kind"] for r in runs_index(loop, key="_decide")]
    assert "task" in dk and "batch" in dk
    dec = next(r for r in runs_index(loop) if r["kind"] == "decide-drop")
    assert open(os.path.join(runs_dir(loop), dec["files"][0]), encoding="utf-8").read() == "方向不对，不做"


def test_multica_run_record_archived(loop):
    loop.multica_project("MB")                                  # 假 multica 认得项目 MB
    loop.add("MB")
    loop.run_until("MB", state_is("merged"), n=12)
    recs = [r for r in runs_index(loop, "MB", "MB-FIX-001") if r["kind"] in ("build-r0", "verify-r0")]
    assert recs and all(r.get("issue") for r in recs)
    runs = [f for r in recs for f in r["files"] if f.endswith(".run.json")]
    assert runs, recs
    j = json.load(open(os.path.join(runs_dir(loop, "MB", "MB-FIX-001"), runs[0]), encoding="utf-8"))
    assert j.get("id") and j.get("status")


# ---------- 2+14 金丝雀 ----------
def test_canary_command_all_cases_judged_right(loop):
    r = loop.evo("canary", "--json")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["ok"] and not d["wrong"], d["wrong"]
    assert d["canaries"] >= 25 and d["total"] > d["canaries"]                    # 有金丝雀也有对照
    checks = {x["check"] for x in d["rows"]}
    for c in ("验收结论 verdict", "验收回报 outcome", "范围 in_scope", "范围 out_of_scope", "交卷 parse_report",
              "交卷 report_red", "全量测试 run_suite", "看效果闸门 look_approved", "决策 parse_decisions"):
        assert c in checks
    sc = json.loads(loop.evo("selfcheck", "--json").stdout)
    assert any(c["name"] == "canary" and c["ok"] for c in sc["checks"])


MUTATIONS = {   # 「先考考官」三变体：改一个常量 / 换一个分支 / 边界挪一位——判据坏了，金丝雀必须报出来
    "常量": ("bin/evo_exec.py", 'VERDICT_PASS = ("pass", "passed", "ok", "succeeded", "通过")',
             'VERDICT_PASS = ("pass", "passed", "ok", "succeeded", "通过", "skipped")', "验收结论 verdict"),
    "分支": ("bin/evo", '    return outcome == "succeeded"\n', '    return outcome in ("succeeded", None, "skipped")\n', "验收回报 outcome"),
    "边界": ("bin/evo", 'p.startswith(x.rstrip("/") + "/")', 'p.startswith(x.rstrip("/"))', "范围 in_scope"),
}


def test_canary_catches_planted_failures(loop, tmp_path):
    for name, (rel, old, new, check) in MUTATIONS.items():
        kit = tmp_path / name
        shutil.copytree(KIT, kit, ignore=shutil.ignore_patterns("tests", "__pycache__", "vendor", "multica", "app"))
        src = open(kit / rel, encoding="utf-8").read()
        assert src.count(old) == 1, (name, old)
        open(kit / rel, "w", encoding="utf-8").write(src.replace(old, new))
        r = subprocess.run([sys.executable, str(kit / "bin" / "evo"), "canary", "--json"], env=loop.env, capture_output=True, text=True)
        d = json.loads(r.stdout)
        assert r.returncode == 1 and not d["ok"], (name, r.stdout[-500:], r.stderr[-500:])
        assert any(w.startswith(check) for w in d["wrong"]), (name, d["wrong"])


def test_verdict_skip_and_unknown_never_pass():
    V = evo_exec.verdict
    assert V('```json\n{"verdict": "pass"}\n```') is True
    for body in ('```json\n{"verdict": "skipped"}\n```\n验收通过', '```json\n{"verdict": "SKIP"}\n```',
                 '```json\n{"verdict": "pending"}\n```\nPASS', '验收通过\n```json\n{"verdict": "fail"}\n```',
                 "未验收通过", "验收跳过", "PASS (skipped)", "", "看起来不错"):
        assert V(body) is False, body
    # 不带 verdict 的 json 块（例如施工报告）不影响结论，接着往前找
    assert V('```json\n{"verdict": "pass"}\n```\n```json\n{"status": "done"}\n```') is True


def test_multica_verify_skipped_verdict_goes_to_rework(loop):
    loop.multica_project("MB")
    loop.plan(verify=["skipped"])
    loop.add("MB")
    loop.run_until("MB", lambda s: s["items"]["MB-FIX-001"]["round"] >= 1, n=12)
    assert loop.item("MB")["state"] != "verified"
    assert any(r["kind"] == "verify-r0" and r["outcome"] == "failed" for r in runs_index(loop, "MB", "MB-FIX-001"))


def test_scope_boundary_is_directory_not_prefix(loop):
    loop.project("AB")
    loop.plan(build=["file:webhooks/x.ts"])
    loop.add("AB", scope="web")
    loop.run_until("AB", lambda s: s["items"][K]["round"] >= 1, n=8)
    ev = [json.loads(l) for l in open(os.path.join(loop.projects, "AB", "state", "timeline.jsonl"), encoding="utf-8")]
    rw = [e for e in ev if e["event"] == "rework"]
    assert rw and "webhooks/x.ts" in rw[0]["why"]


def test_all_skipped_suite_is_not_green(loop):
    loop.project("AB", test_cmd="echo '========== 4 skipped in 0.02s =========='")   # 退出码 0，但一个测试都没真跑
    loop.add("AB")
    loop.run_until("AB", lambda s: bool(s.get("main_red")), n=10)
    st = loop.state("AB")
    assert st["items"][K]["state"] != "merged"                                     # 跳过不算通过：不合并
    fix = [it for it in st["items"].values() if it.get("fixes_main")]
    assert fix and "跳过不算通过" in fix[0]["spec"]                                  # 主线也算红，登记一件修主线


# ---------- 4 施工只拿施工的东西 ----------
def test_every_build_task_book_starts_with_role_declaration(loop):
    loop.project("AB", goal="让布艺店主十分钟上架一款新品")
    loop.plan(verify=["fail"], build=["ok", "die"])
    loop.add("AB")
    loop.run_until("AB", lambda s: s["items"][K]["round"] >= 1 and s["items"][K]["state"] in ("building", "built", "verifying", "verified", "merged"), n=10)
    for _ in range(3):
        loop.tick("AB")
    builds = [w["spec"] for w in loop.workers() if w["role"] == "build"]
    assert len(builds) >= 2
    for sp in builds + [loop.item("AB")["build_spec"]]:
        assert sp.startswith(DECL), sp[:120]
        assert not any(m in sp for m in DECIDER_MARKS)
    for w in loop.workers():
        if w["role"] == "verify":
            assert DECL not in w["spec"] and not any(m in w["spec"] for m in DECIDER_MARKS)


def test_misconfigured_build_prompt_never_hands_decider_rules_to_builder(loop):
    loop.write_global({"roles": {"build": {"prompt": "roles/decider.md"}}})
    loop.project("AB")
    r = loop.add("AB")
    b = loop.item("AB")["build_spec"]
    assert b.startswith(DECL) and not any(m in b for m in DECIDER_MARKS)
    assert "施工岗" in b                                                         # 退回套件自带的施工岗规则
    assert "决策岗专属规则" in r.stderr


def test_old_state_build_spec_gets_declaration_on_redispatch(loop):
    loop.project("AB")
    loop.plan(build=["die"])
    loop.add("AB")
    p = os.path.join(loop.projects, "AB", "state", "state.json")
    s = json.load(open(p, encoding="utf-8"))
    s["items"][K]["build_spec"] = s["items"][K]["build_spec"].replace(DECL + "\n\n", "")   # 第二十二轮前的老状态
    json.dump(s, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    for _ in range(4):
        loop.tick("AB")
    builds = [w["spec"] for w in loop.workers() if w["role"] == "build"]
    assert len(builds) >= 2 and builds[-1].startswith(DECL)


# ---------- 6 推送问远端 ----------
def test_push_exit_zero_but_remote_unchanged_is_not_merged(loop):
    loop.project("AB", push_cmd="true")                       # 推送命令说成功，其实什么都没推
    before = loop.remote_head("AB")
    loop.add("AB")
    loop.run_until("AB", state_is("pushing"), n=10)
    for _ in range(2):
        loop.tick("AB")
    st = loop.state("AB")
    assert st["items"][K]["state"] == "pushing" and loop.remote_head("AB") == before
    assert any("远端没有这个提交" in l for l in st["log"])
    loop.patch_cfg("AB", push_cmd="git push origin main")      # 修好推送命令：下一轮推上去、问远端确认后才算合并
    loop.run_until("AB", state_is("merged"), n=4)
    assert loop.item("AB")["pushed"] == loop.remote_head("AB")


def test_push_verify_off_keeps_old_behavior(loop):
    loop.project("AB", push_cmd="true", push_verify=False)
    loop.add("AB")
    loop.run_until("AB", state_is("merged"), n=10)


def test_push_confirm_uses_remote_named_in_push_cmd(loop):
    loop.project("AB")
    other = os.path.join(loop.tmp, "repos", "AB", "backup.git")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", other], check=True, env=loop.env)
    repo = loop.repo("AB")
    loop.git(repo, "remote", "add", "backup", other)
    loop.git(repo, "push", "-q", "backup", "main")
    loop.patch_cfg("AB", push_cmd="git push backup main")
    loop.add("AB")
    loop.run_until("AB", state_is("merged"), n=10)
    head = loop.item("AB")["pushed"]
    assert loop.git(other, "rev-parse", "main") == head
    push = next(r for r in runs_index(loop) if r["kind"] == "push")
    assert push["remote"] == "backup"
