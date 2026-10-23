"""第二十五轮（架构减法）：#26 老板卡收成三类。"""
import json
import os

K = "MB-FIX-001"


def _plant(loop, code, box, gid, entry, options):
    """往老状态里放一张旧类别的卡（第二十五轮前的写法），执行端账本里放一个还在等的闸门。"""
    sd = os.path.join(loop.projects, code, "state")
    lp = os.path.join(sd, "exec-multica.json")
    L = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else {"n": 0, "tasks": {}, "gates": {}, "dispatches": {}, "issues": {}, "agent_ids": {}, "project_id": None}
    L.setdefault("gates", {})[gid] = {"id": gid, "task": None, "question": f"老卡 {box}", "options": options,
                                      "status": "pending", "resolution": None}
    json.dump(L, open(lp, "w", encoding="utf-8"), ensure_ascii=False)
    s = loop.state(code)
    s.setdefault(box, {})[gid] = entry
    json.dump(s, open(os.path.join(sd, "state.json"), "w", encoding="utf-8"), ensure_ascii=False)


def test_legacy_gate_boxes_read_as_do_cards(loop):
    """旧 state 里的 owner_asks / ext_gates / budget_gates 读出来都是 do 卡，一张不丢，选项统一做 / 不做。"""
    loop.multica_project("MB")
    loop.add("MB")
    _plant(loop, "MB", "owner_asks", "mg_81", {"key": K, "task": None, "note": "要不要删旧表"}, ["同意", "不同意"])
    _plant(loop, "MB", "budget_gates", "mg_82", {"key": K, "task": None, "why": "已派工 12 次还没完", "rework": None}, ["继续", "不做"])
    _plant(loop, "MB", "ext_gates", "mg_83", {"key": "#7", "task": None, "red": ["删数据"],
                                               "report": {"issue": "7", "title": "清库", "trusted": False}}, ["同意交决策岗", "拒绝"])
    st = json.loads(loop.ok("-p", "MB", "status", "--json").stdout)
    g = {x["id"]: x for x in st["gates"]}
    assert {"mg_81", "mg_82", "mg_83"} <= set(g)
    assert all(g[i]["kind"] == "do" and g[i]["options"] == ["做", "不做"] for i in ("mg_81", "mg_82", "mg_83"))
    assert (g["mg_81"]["reason"], g["mg_82"]["reason"], g["mg_83"]["reason"]) == ("decider", "budget", "external")
    assert g["mg_81"]["item"] == K and g["mg_83"]["item"] == "#7"
    assert {x["kind"] for x in st["gates"]} <= {"do", "look", "ship", "other"}
    # 写操作一跑，老表并进 do_gates 落盘；老按钮的「同意」照旧等同做
    loop.ok("-p", "MB", "approve", "mg_81", "同意", "留着")
    s = loop.state("MB")
    assert not any(b in s for b in ("owner_asks", "ext_gates", "budget_gates"))
    assert set(s["do_gates"]) == {"mg_82", "mg_83"} and s["do_gates"]["mg_82"]["why"] == "budget"
    assert s["do_gates"]["mg_82"]["note"] == "已派工 12 次还没完"
    assert "老板答复" in loop.item("MB")["ask"] and "：做" in loop.item("MB")["ask"]
    loop.ok("-p", "MB", "approve", "mg_83", "不做", "不许删")
    s = loop.state("MB")
    assert "mg_83" not in s["do_gates"] and not any(e.get("issue") == "7" for e in s.get("decide_inbox") or [])


def test_status_schema_has_three_gate_kinds():
    """合约：kind 只剩 do / look / ship（other 兜底），来由在 reason。决策岗转老板的完整流程见 test_round10。"""
    schema = json.load(open(os.path.join(os.path.dirname(__file__), "..", "schemas", "status.schema.json"), encoding="utf-8"))
    props = schema["properties"]["gates"]["items"]["properties"]
    assert set(props["kind"]["enum"]) == {"do", "look", "ship", "other"}
    assert {"decider", "external", "budget"} <= set(props["reason"]["enum"])


# ---------- #27 件号直接用 GitHub issue 号 ----------
def _state_is(st):
    return lambda s: all(it["state"] == st for it in s["items"].values())


def test_issue_number_is_the_key_and_commands_accept_it(loop):
    loop.project("AB")
    loop.add("AB", extra=["--issue", "29"])
    assert list(loop.state("AB")["items"]) == ["AB#29"]
    loop.add("AB", "修复设置页保存失败", "api/", ["--issue", "#29"])       # 同一个 issue 再登记一件
    assert list(loop.state("AB")["items"]) == ["AB#29", "AB#29-2"]
    for ref in ("AB#29", "29", "#29", "ab#29"):
        assert json.loads(loop.ok("-p", "AB", "log", ref, "--json").stdout)["key"] == "AB#29"
    assert json.loads(loop.ok("-p", "AB", "runs", "29", "--json").stdout)["key"] == "AB#29"
    loop.ok("-p", "AB", "drop", "#29", "测试")
    assert loop.state("AB")["items"]["AB#29"]["state"] == "dropped"
    assert loop.state("AB")["items"]["AB#29-2"]["state"] != "dropped"
    assert not loop.state("AB").get("seq_kind")                          # 有 issue 的件不再取序号


def test_issue_key_goes_through_the_whole_loop(loop):
    """件号里带 #：工作区、分支、合并提交信息都要能走通（假 Orca）。"""
    loop.project("AB")
    loop.add("AB", extra=["--issue", "7"])
    st = loop.run_until("AB", _state_is("merged"))
    assert st["items"]["AB#7"]["merged_sha"]
    msg = __import__("subprocess").run(["git", "-C", loop.repo("AB"), "log", "-1", "--format=%s", st["items"]["AB#7"]["merged_sha"]],
                                        capture_output=True, text=True).stdout
    assert "AB#7" in msg


def test_issue_key_multica(loop):
    loop.multica_project("MB")
    loop.add("MB", extra=["--issue", "31"])
    st = loop.run_until("MB", _state_is("merged"), n=10)
    assert list(st["items"]) == ["MB#31"]


def test_no_issue_falls_back_to_local_key_and_new_issue_flag(loop):
    loop.project("AB", github_repo="o/r")
    r = loop.add("AB")
    assert list(loop.state("AB")["items"]) == ["AB-FIX-001"] and "本地件号" in r.stdout   # 没 issue：退回老格式
    json.dump(41, open(os.path.join(loop.orca_dir, "gh_next_issue"), "w"))
    loop.add("AB", "修复设置页保存失败", "api/", ["--new-issue"])
    assert "AB#41" in loop.state("AB")["items"]
    gh = open(os.path.join(loop.orca_dir, "gh.log"), encoding="utf-8").read()
    assert "issue create -R o/r --title 修复设置页保存失败" in gh


def test_old_keys_still_work_and_resolve_by_issue(loop):
    """老件（TB-FIX-012 这种）原样可读可操作；挂着 issue 的老件用 issue 号也能找到。"""
    loop.project("AB")
    loop.add("AB")
    sd = os.path.join(loop.projects, "AB", "state", "state.json")
    s = loop.state("AB")
    s["items"]["AB-FIX-001"]["issue"] = "12"                            # 第二十五轮前登记的、挂着 issue 12 的老件
    json.dump(s, open(sd, "w", encoding="utf-8"), ensure_ascii=False)
    assert json.loads(loop.ok("-p", "AB", "log", "AB-FIX-001", "--json").stdout)["key"] == "AB-FIX-001"
    assert json.loads(loop.ok("-p", "AB", "log", "#12", "--json").stdout)["key"] == "AB-FIX-001"
    loop.ok("-p", "AB", "feedback", "--item", "12", "按钮再大一点")
    assert "按钮再大一点" in loop.item("AB")["spec"]
    loop.ok("-p", "AB", "drop", "12")
    assert loop.item("AB")["state"] == "dropped"


def test_title_with_key_or_issue_number_rejected(loop):
    loop.project("AB")
    for t in ("AB-FIX-9 修复登录", "#29 修复登录", "AB#29 修复登录"):
        r = loop.evo("-p", "AB", "add", "--kind", "fix", "--title", t, "--scope", "web/")
        assert r.returncode != 0 and "issue 号" in (r.stderr + r.stdout)
