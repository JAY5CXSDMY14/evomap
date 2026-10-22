"""第二十一轮：Claude 接入准备——决策岗新动作 propose（架构提议），Orca / Multica 两种执行端都走。

提议登记成一件带 proposal 标签的件，note 原样当任务书，一律挂老板「做不做」闸门；老板点「做」之前不派工；
每个项目同时最多 3 件没完结的提议，多的记日志和时间线后跳过。
"""
import json, os, sys

from conftest import KIT, state_is

WORKER = os.path.join(KIT, "tests", "fakes", "worker.py")
K = "AB-FIX-001"
NOTE = "想改：派工改成事件驱动\n为什么：轮询浪费额度\n不改的代价：夜里多烧 30% 额度\n现成方案：watchdog（Apache-2.0）"


def with_decider(loop, **lim):
    loop.write_global({"roles": {"decide": {"cmd": f"{sys.executable} {WORKER} decide", "models": ["model-x"],
                                            "prompt": "roles/decider.md", "boot_seconds": 0}},
                       "limits": {"rework_rounds": 0, "decide_every_minutes": 0, **lim}})


def escalate_then(loop, code, *decisions, multica=False, **lim):
    """验收一次不过就交决策岗；决策岗交出 decisions，等到这批决定执行完。"""
    with_decider(loop, **lim)
    (loop.multica_project if multica else loop.project)(code)
    loop.plan(verify=["fail"], decide=[{"decisions": list(decisions)}])
    loop.add(code)
    loop.run_until(code, lambda s: s["items"][f"{code}-FIX-001"]["state"] == "escalated"
                   and any("决策岗批次做完" in l for l in s["log"]), n=10)


def proposals(loop, code):
    return {k: it for k, it in loop.state(code)["items"].items() if it.get("proposal")}


def timeline(loop, code):
    p = os.path.join(loop.projects, code, "state", "timeline.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def builds_for(loop, key, code="AB"):
    return (loop.state(code)["items"][key].get("dispatch") or {}).get("build")


def test_propose_registers_gated_item_and_waits_for_owner(loop):
    escalate_then(loop, "AB", {"item": K, "action": "propose", "note": NOTE})
    ps = proposals(loop, "AB")
    assert list(ps) == ["AB-CHORE-001"]
    p = ps["AB-CHORE-001"]
    assert p["title"].startswith("架构提议：") and len(p["title"]) <= 24
    assert p["labels"] == ["proposal"] and p["parent"] == K and p["scope"] == ["docs/proposals/"]
    assert NOTE in p["spec"] and "老板点「做」才开工" in p["spec"]
    assert p["gates"].get("do") and p["state"] == "queued"
    gates = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "do"]
    assert len(gates) == 1 and gates[0]["item"] == "AB-CHORE-001"
    st = [i for i in loop.status_json("AB")["items"] if i["key"] == "AB-CHORE-001"][0]
    assert st["labels"] == ["proposal"]
    for _ in range(3):                                     # 老板没点：怎么转都不开工
        loop.tick("AB")
    assert loop.state("AB")["items"]["AB-CHORE-001"]["state"] == "queued" and not builds_for(loop, "AB-CHORE-001")
    assert any(e["event"] == "proposal" and e["item"] == "AB-CHORE-001" for e in timeline(loop, "AB"))
    loop.ok("-p", "AB", "approve", gates[0]["id"], "做")
    loop.run_until("AB", lambda s: s["items"]["AB-CHORE-001"]["state"] == "merged", n=10)
    assert builds_for(loop, "AB-CHORE-001")


def test_propose_without_item_uses_given_title_scope_and_kind(loop):
    escalate_then(loop, "AB", {"item": "-", "action": "propose", "note": NOTE, "title": "改成事件驱动派工",
                               "scope": ["kit/bin/"], "kind": "feat"})
    ps = proposals(loop, "AB")
    assert list(ps) == ["AB-FEAT-001"]
    p = ps["AB-FEAT-001"]
    assert p["title"] == "改成事件驱动派工" and p["scope"] == ["kit/bin/"] and p["parent"] is None
    assert p["gates"].get("do")
    assert loop.state("AB")["items"][K]["state"] == "escalated"          # 提议不动原件


def test_propose_bad_title_falls_back_and_missing_reuse_line_is_logged(loop):
    escalate_then(loop, "AB", {"item": K, "action": "propose", "note": "派工改成事件驱动\n轮询浪费\n多烧额度",
                               "title": "AB-FIX-9 改v2草案"})
    p = next(iter(proposals(loop, "AB").values()))
    assert p["title"] == "架构提议：派工改成事件驱动"
    assert any("没写「现成方案」" in l for l in loop.state("AB")["log"])


def test_propose_rate_limit_and_duplicates(loop):
    ds = [{"item": "-", "action": "propose", "note": NOTE, "title": f"提议改法第{n}种"} for n in "一二三四"]
    ds.append({"item": "-", "action": "propose", "note": NOTE, "title": "提议改法第一种"})
    escalate_then(loop, "AB", *ds)
    ps = proposals(loop, "AB")
    assert sorted(p["title"] for p in ps.values()) == ["提议改法第一种", "提议改法第三种", "提议改法第二种"]
    st = loop.state("AB")
    assert any("提议「提议改法第四种」没登记" in l and "上限 3" in l for l in st["log"])
    assert any("已经在等老板" in l for l in st["log"])
    skipped = [e for e in timeline(loop, "AB") if e["event"] == "proposal_skipped"]
    assert len(skipped) == 2 and skipped[0]["item"] == "-"


def test_propose_cap_is_configurable(loop):
    ds = [{"item": "-", "action": "propose", "note": NOTE, "title": f"提议改法第{n}种"} for n in "一二"]
    escalate_then(loop, "AB", *ds, open_proposals=1)
    assert [p["title"] for p in proposals(loop, "AB").values()] == ["提议改法第一种"]


def test_propose_on_multica_is_gated_too(loop):
    escalate_then(loop, "MB", {"item": "MB-FIX-001", "action": "propose", "note": NOTE}, multica=True)
    ps = proposals(loop, "MB")
    assert list(ps) == ["MB-CHORE-001"]
    p = ps["MB-CHORE-001"]
    assert p["gates"].get("do") and p["state"] == "queued" and p["exec"]["backend"] == "multica"
    gates = [g for g in loop.status_json("MB")["gates"] if g["kind"] == "do"]
    assert len(gates) == 1 and gates[0]["item"] == "MB-CHORE-001"
    for _ in range(3):
        loop.tick("MB")
    assert loop.state("MB")["items"]["MB-CHORE-001"]["state"] == "queued"
    assert not loop.state("MB")["items"]["MB-CHORE-001"]["exec"].get("issue")      # 没批之前不建 issue、不派工
    loop.ok("-p", "MB", "approve", gates[0]["id"], "做")
    loop.run_until("MB", lambda s: s["items"]["MB-CHORE-001"]["state"] == "merged", n=10)


def test_decider_role_file_has_three_tiers_and_propose():
    for name in ("decider", "builder", "verifier", "retro"):
        t = open(os.path.join(KIT, "roles", f"{name}.md"), encoding="utf-8").read()
        assert "【红线】" in t and "【接口】" in t and "【现状】" in t and "不是定论" in t, name
    d = open(os.path.join(KIT, "roles", "decider.md"), encoding="utf-8").read()
    assert "`propose`" in d and "现成方案" in d
    assert "不重复造轮子" in open(os.path.join(KIT, "roles", "builder.md"), encoding="utf-8").read()
    assert "重复造轮子" in open(os.path.join(KIT, "roles", "verifier.md"), encoding="utf-8").read()
