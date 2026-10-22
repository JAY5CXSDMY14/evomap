"""第二十轮：Multica 执行端（kit/bin/evo_exec.py · MulticaExecutor）。设计见 docs/multica-backend.md。

假 multica（tests/fakes/multica）在 assign / rerun 时同步跑假工人；施工在 agent/dsh/<issue> 分支上提交，
evo 交卷时把分支取进自己的克隆（evo/<件号>），验收 / 看效果 / 合并 / 推送照旧在 evo 这边。
"""
import json, os

from conftest import state_is

K = "MB-FIX-001"


def issues(loop):
    return list(loop.multica_state()["issues"].values())


def runs(loop, role=None):
    ag = {"build": "ag-build", "verify": "ag-verify", "decide": "ag-decide"}
    return [r for r in loop.multica_state()["runs"] if not role or r["agent_id"] == ag[role]]


def calls(loop):
    return [" ".join(c) for c in loop.multica_state()["calls"]]


def test_dispatch_to_in_review_verify_pass_merge_push(loop):
    loop.multica_project("MB")
    loop.add("MB")
    it = loop.item("MB")
    assert it["exec"]["backend"] == "multica" and loop.state("MB")["schema_version"] == 2
    st = loop.run_until("MB", state_is("merged"))
    it = st["items"][K]
    iss = issues(loop)
    assert len(iss) == 1 and it["exec"]["issue"] == iss[0]["identifier"]          # 一件 = 一个 issue（施工、验收同一个）
    assert it["exec"]["branch"] == f"agent/dsh/{iss[0]['identifier'].lower()}"
    assert iss[0]["status"] == "done"                                             # 合并后 issue 收尾
    assert len(runs(loop, "build")) == 1 and len(runs(loop, "verify")) == 1
    assert it["pushed"] == loop.remote_head("MB")
    assert any(f.startswith("web/change-") for f in loop.remote_files("MB"))
    # 派工全走 issue assign；没有任何 orca 编排调用（10-22 决策岗超时的 --inject 路径不再出现）
    assert any(c.startswith("issue assign") for c in calls(loop))
    orca = os.path.join(loop.orca_dir, "state.json")
    assert not os.path.exists(orca) or not [c for c in json.load(open(orca))["calls"] if c[0] in ("orchestration", "terminal")]
    # 验收规格作为评论追加在同一个 issue 上
    cs = [c for c in loop.multica_state()["comments"] if c["author_type"] == "member"]
    assert any("验收" in c["content"] and "verdict" in c["content"] for c in cs)
    s = loop.status_json("MB")
    assert s["items"][0]["state"] == "已合并·可收菜"


def test_verify_fail_reworks_on_same_issue_then_passes(loop):
    loop.multica_project("MB")
    loop.plan(verify=["fail"])
    loop.add("MB")
    st = loop.run_until("MB", state_is("merged"), n=10)
    it = st["items"][K]
    assert it["round"] == 1
    assert len(issues(loop)) == 1                                                 # 返工不另开 issue
    assert len(runs(loop, "build")) == 2 and len(runs(loop, "verify")) == 2
    builds = [w for w in loop.workers() if w["role"] == "build"]
    assert "验收不通过" in builds[1]["spec"]                                       # 返工原因随评论送到施工
    assert it["pushed"] == loop.remote_head("MB")


def test_rework_cap_escalates(loop):
    loop.multica_project("MB")
    loop.plan(verify=["fail", "fail", "fail"])
    loop.add("MB")
    st = loop.run_until("MB", state_is("escalated"), n=14)
    assert st["items"][K]["round"] == 3
    assert len(runs(loop, "verify")) == 3
    assert "需要决策" in loop.notifications()


def test_comment_trigger_does_not_double_dispatch(loop):
    loop.multica_project("MB")
    os.makedirs(os.path.join(loop.orca_dir, "multica"), exist_ok=True)
    open(os.path.join(loop.orca_dir, "multica", "comment-triggers"), "w").close()   # 留言本身就会叫醒 agent
    loop.add("MB")
    loop.run_until("MB", state_is("merged"))
    assert len(runs(loop, "verify")) == 1                                         # 留言叫醒了就不再 rerun
    assert not any(c.startswith("issue rerun") for c in calls(loop))


def test_decider_batch_is_an_issue_and_its_json_is_executed(loop):
    loop.write_global({"limits": {"rework_rounds": 0, "decide_every_minutes": 0}})
    loop.multica_project("MB")
    loop.plan(verify=["fail"], decide=[{"decisions": [{"item": K, "action": "drop", "note": "需求已取消"}]}])
    loop.add("MB")
    st = loop.run_until("MB", state_is("dropped"), n=10)
    dec = [i for i in issues(loop) if "决策批次" in i["title"]]
    assert len(dec) == 1 and dec[0]["status"] == "done"                           # 决策批次 = 一个 issue，派给决策 agent
    assert len(runs(loop, "decide")) == 1
    assert "交给你的事" in dec[0]["description"]
    item_iss = [i for i in issues(loop) if i["identifier"] == st["items"][K]["exec"]["issue"]]
    assert item_iss and item_iss[0]["status"] == "cancelled"                      # 不做：issue 标 cancelled


def test_decider_rework_cap_goes_to_owner(loop):
    loop.write_global({"limits": {"rework_rounds": 0, "decider_reworks": 1, "decide_every_minutes": 0}})
    loop.multica_project("MB")
    rw = {"decisions": [{"item": K, "action": "rework", "note": "换个写法"}]}
    loop.plan(verify=["fail", "fail", "pass"], decide=[rw, rw])
    loop.add("MB")
    for _ in range(10):
        loop.tick("MB")
        if loop.item("MB").get("hold"):
            break
    it = loop.item("MB")
    assert it.get("hold") and it["decider_reworks"] == 1
    loop.ok("-p", "MB", "approve", it["hold"], "继续")                          # 上限闸门在 evo 自己的账本里
    assert loop.item("MB")["state"] == "queued"
    loop.run_until("MB", state_is("merged"), n=10)


def test_daemon_down_pushes_once_and_resumes(loop):
    loop.multica_project("MB")
    loop.add("MB")
    down = os.path.join(loop.orca_dir, "multica", "daemon-down")
    os.makedirs(os.path.dirname(down), exist_ok=True)
    open(down, "w").close()
    loop.tick("MB"); loop.tick("MB")
    assert loop.item("MB")["state"] == "queued"                                   # 掉线：不派工
    assert not issues(loop)
    assert loop.notifications().count("执行端掉线") == 1                           # 只推一次
    assert "执行端掉线" in loop.ok("-p", "MB", "status").stdout
    assert loop.status_json("MB")["orca_down_since"]                              # App 合约字段名不变
    os.remove(down)
    loop.run_until("MB", state_is("merged"))
    assert not loop.status_json("MB")["orca_down_since"]


def test_server_down_counts_as_exec_down(loop):
    loop.multica_project("MB")
    loop.add("MB")
    p = os.path.join(loop.orca_dir, "multica", "server-down")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()
    loop.tick("MB")
    assert loop.item("MB")["state"] == "queued"
    assert "服务端连不上" in json.dumps(loop.state("MB")["log"], ensure_ascii=False)


def test_build_ratelimit_requeues_without_counting_rework(loop):
    loop.multica_project("MB")
    loop.plan(build=["ratelimit"])
    loop.add("MB")
    loop.tick("MB"); loop.tick("MB")
    it = loop.item("MB")
    assert it["round"] == 0 and it.get("rate_waits") == 1
    assert "额度" in loop.notifications()


def test_build_question_goes_to_asking(loop):
    loop.multica_project("MB")
    loop.plan(build=["ask"])
    loop.add("MB")
    loop.run_until("MB", state_is("asking"))
    assert "配色" in loop.item("MB")["ask"]


def test_schema_migration_and_reseed_from_orca(loop):
    """老项目（Orca、没有 schema_version）换到 Multica：exec 字段补上、Orca 任务号进 exec.legacy、没做完的件在新执行端重建。"""
    loop.project("MB")
    loop.add("MB")
    p = os.path.join(loop.projects, "MB", "state", "state.json")
    st = json.load(open(p, encoding="utf-8"))
    st.pop("schema_version", None)
    for it in st["items"].values():
        it.pop("exec", None)
    json.dump(st, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    old = st["items"][K]["build"]
    loop.patch_cfg("MB", executor="multica", multica={"project": "MB"})
    loop.env["FAKE_MULTICA_REPO"] = loop.repo("MB")
    loop.tick("MB")
    it = loop.item("MB")
    assert loop.state("MB")["schema_version"] == 2
    assert it["exec"]["legacy"]["build"] == old and it["exec"]["backend"] == "multica"
    assert it["build"] != old
    loop.run_until("MB", state_is("merged"))


def test_orca_project_without_key_stays_orca(loop):
    loop.project("AB")                       # 测试全局配置 executor=orca；项目配置里写的是 import 时的选择
    c = json.load(open(loop.cfg_path("AB")))
    assert c["executor"] == "orca"
    c.pop("executor"); json.dump(c, open(loop.cfg_path("AB"), "w"))
    loop.write_global({"executor": None})
    loop.add("AB")
    loop.run_until("AB", state_is("merged"))
    assert not issues(loop)


def test_new_project_defaults_to_multica(loop):
    loop.write_global({"executor": None})
    loop.project("MC")
    c = json.load(open(loop.cfg_path("MC")))
    assert c["executor"] == "multica" and c["multica"]["agents"]["decide"] == "决策-Claude"


def test_status_json_carries_issue_link(loop):
    loop.multica_project("MB")
    loop.add("MB")
    loop.tick("MB")
    item = loop.status_json("MB")["items"][0]
    ident = loop.item("MB")["exec"]["issue"]
    assert item["exec"] == {"backend": "multica", "issue": ident, "url": f"http://multica.test/issues/{ident}"}


def test_owner_drop_before_switch_is_not_reseeded(loop):
    """10-22 Air：EV 两件老件卡在 Orca，切 Multica 前老板先 drop，切换后不在 Multica 里重跑。"""
    loop.project("MB")
    loop.add("MB")
    loop.patch_cfg("MB", executor="multica", multica={"project": "MB"})
    loop.env["FAKE_MULTICA_REPO"] = loop.repo("MB")
    r = loop.evo("-p", "MB", "drop", K, "切换前清掉")
    assert r.returncode == 0, r.stderr
    loop.tick("MB")
    it = loop.item("MB")
    assert it["state"] == "dropped" and not issues(loop)
    assert it["exec"]["legacy"]["from"] == "orca"
