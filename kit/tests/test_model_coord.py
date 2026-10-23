"""第十四轮：模型协调。岗位卡片、evo team、健康检查（缓存 5 分钟）、额度满切备用 / 到点切回、
模型下线或不认识 → 停岗位、magpie 不通、施工≠验收（含组成员）、每个模型的成绩和建议、新模型发现、
evo team set / clear / trial / init（外部 Agent 一律拒绝）、status --json 的 team、面板 /api/team。"""
import json, os, stat, sys

from conftest import KIT, WORKER, state_is
from test_agents_panel import req
from test_round11 import start_panel

sys.path.insert(0, os.path.join(KIT, "bin"))
sys.path.insert(0, os.path.join(KIT, "features", "team"))   # 第十八轮：团队搬成功能包
import evo_team as TEAM     # noqa: E402

PY = sys.executable
K = "AB-FIX-001"
NOON = "2026-10-20T12:00:00+08:00"


def mag(*ids, extra=None):
    return {"object": "list", "data": [{"id": i} for i in ids] + list(extra or [])}


def roles(loop, **cards):
    """改全局岗位卡片（在 conftest 默认卡片上合并）。"""
    p = os.path.join(loop.root, "config.json")
    g = json.load(open(p))
    for r, c in cards.items():
        if c is None:
            g["roles"].pop(r, None)
        else:
            g["roles"][r] = {**(g["roles"].get(r) or {}), **c}
    json.dump(g, open(p, "w"), ensure_ascii=False)


def gcfg(loop):
    return json.load(open(os.path.join(loop.root, "config.json")))


def team(loop, *args):
    return json.loads(loop.ok(*args, "team", "--json").stdout)


def card(doc, role):
    return next(c for c in doc["cards"] if c["role"] == role)


def kinds(loop):
    return [e["kind"] for e in loop.outbox()]


def magpie_probes(loop):
    return [x for x in loop.http_log() if x["url"].endswith("/v1/models")]


def fallback_build(loop, **extra):
    roles(loop, build={"tool": "primary", "fallback": {"tool": "backup", "cmd": f"{PY} {WORKER} build --fb {{model}}",
                                                       "models": ["fb-model"], **extra}})


# ---------- 纯逻辑 ----------
def test_render_cmd_fills_and_drops_empty_flags():
    assert TEAM.render_cmd("codex --model {model} -c model_reasoning_effort={thinking}", "gpt-5", "high") == \
        "codex --model gpt-5 -c model_reasoning_effort=high"
    assert TEAM.render_cmd("codex --model {model} -c model_reasoning_effort={thinking}", None, None) == "codex"
    assert TEAM.render_cmd("pi --model={model} --thinking {thinking}", "x", None) == "pi --model=x"
    assert TEAM.render_cmd("dsh", "m", "high") == "dsh"                     # 没有占位符：原样


def test_via_and_account_rules():
    assert TEAM.via_of({"models": ["group/evo-build"]}) == "magpie" and TEAM.via_of({"models": ["glm"]}) == "cli"
    assert TEAM.via_of({"via": "magpie", "models": []}) == "magpie"
    assert TEAM.account_of({"cmd": "codex --model x"}) == "codex" and TEAM.account_of({"tool": "pi", "cmd": "x"}) == "pi"
    fb = TEAM.fallback_rc({"cmd": "codex", "fallback": {"tool": "dsh", "models": ["group/evo-build"]}})
    assert fb["cmd"] == TEAM.TOOL_CMDS["dsh"] and fb["models"] == ["group/evo-build"] and TEAM.account_of(fb) == "dsh"
    assert TEAM.fallback_rc({"cmd": "codex"}) is None


def rec(item, event, at, project="AB", **kw):
    return {"at": f"2026-10-{at}T12:00:00+08:00", "item": item, "event": event, "project": project, **kw}


def history(model, n, rejects, look_rejects=0, verify="vv", day=10):
    """n 件：每件施工一次（同一模型），前 rejects 件验收先打回、返工一次；前 look_rejects 件老板看效果打回。"""
    out = []
    for i in range(n):
        it = f"AB-FIX-{model}{i}"
        d = f"{day:02d}"
        out += [rec(it, "dispatch", d, role="build", model=model, dispatch=f"b{model}{i}")]
        out += [rec(it, "report", d, role="build", outcome="succeeded", dispatch=f"b{model}{i}")]
        out += [rec(it, "dispatch", d, role="verify", model=verify, dispatch=f"v{model}{i}")]
        if i < rejects:
            out += [rec(it, "report", d, role="verify", outcome="failed", dispatch=f"v{model}{i}"), rec(it, "rework", d, round=1),
                    rec(it, "dispatch", d, role="build", model=model, dispatch=f"b2{model}{i}"),
                    rec(it, "dispatch", d, role="verify", model=verify, dispatch=f"v2{model}{i}")]
        out += [rec(it, "report", d, role="verify", outcome="succeeded", dispatch=f"v2{model}{i}" if i < rejects else f"v{model}{i}")]
        if i < look_rejects:
            out += [rec(it, "gate_reject", d, kind="look")]
        else:
            out += [rec(it, "gate_approve", d, kind="look"), rec(it, "merge", d, sha="x")]
    return out


def test_model_stats_from_timeline():
    st = TEAM.model_stats(history("glm", 6, 3, 2) + [rec("AB-FIX-glm0", "no_live_path", "11", reason="stalled")])
    b = st["glm"]["build"]
    assert b["items"] == 6 and b["verify_reject_rate"] == round(3 / 9, 3) and b["rework_per_item"] == 0.5
    assert b["look_reject_rate"] == round(2 / 6, 3) and b["no_live_path"] == 1 and b["merged"] == 4
    v = st["vv"]["verify"]
    assert v["rejects"] == 3 and v["passes"] == 6 and v["escaped"] == 2 and v["escape_rate"] == round(2 / 6, 3)


def test_recommendation_needs_samples_and_never_switches():
    few = TEAM.model_stats(history("glm", 3, 2))
    assert TEAM.recommend("build", "glm", few)["switch_to"] is None and "数据还少" in TEAM.recommend("build", "glm", few)["text"]
    st = TEAM.model_stats(history("glm", 6, 4, 2) + history("ds", 6, 0, 0))
    r = TEAM.recommend("build", "glm", st)
    assert r["switch_to"] == "ds" and "建议施工换成 ds" in r["text"] and "才生效" in r["text"]
    assert TEAM.recommend("build", "ds", st)["switch_to"] is None                       # 当前已是最好的
    st = TEAM.model_stats(history("a", 6, 0, 3, verify="v1") + history("b", 6, 0, 0, verify="v2"))
    assert TEAM.recommend("verify", "v1", st)["switch_to"] == "v2"                     # 漏放少的验收模型


def test_decide_card_warns_when_not_strong():
    w = TEAM.card_warnings("decide", {"cmd": "claude", "models": ["glm-4-flash"]}, {}, {})
    assert any("最强" in x for x in w)
    assert not TEAM.card_warnings("decide", {"cmd": "claude", "models": ["claude-opus-4"]}, {}, {})
    assert not TEAM.card_warnings("decide", {"cmd": "claude", "models": ["cheap"]}, {}, {}, tiers={"cheap": "strong"})


# ---------- evo team：卡片 + 健康 ----------
def fake_cli(loop, *names):
    d = os.path.join(loop.tmp, "clibin")
    os.makedirs(d, exist_ok=True)
    for n in names:
        p = os.path.join(d, n)
        open(p, "w").write("#!/bin/sh\nexit 0\n"); os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    loop.env["PATH"] = d + os.pathsep + loop.env["PATH"]


def test_team_cards_fields_and_health(loop):
    fake_cli(loop, "claude", "codex")
    os.makedirs(os.path.join(loop.env["HOME"], ".claude"), exist_ok=True)
    open(os.path.join(loop.env["HOME"], ".claude", ".credentials.json"), "w").write("{}")
    roles(loop, verify={"tool": "claude", "thinking": "high", "duty": "换模型从头核对", "via": "cli"},
          decide={"tool": "codex", "cmd": "codex --model {model}", "models": ["gpt-5"], "prompt": "roles/decider.md"})
    loop.http_responses({"/v1/models": [mag("group/evo-build", "glm")]})
    d = team(loop)
    assert d["schema_version"] == 1 and d["magpie"]["ok"] and d["magpie"]["groups"] == ["group/evo-build"]
    assert d["clis"]["claude"] == {"installed": True, "path": d["clis"]["claude"]["path"], "logged_in": True}
    assert d["clis"]["codex"]["logged_in"] is False and d["clis"]["dsh"]["installed"] is False
    v = card(d, "verify")
    assert v["tool"] == "claude" and v["thinking"] == "high" and v["duty"] == "换模型从头核对" and v["status"]["label"] == "可用"
    dc = card(d, "decide")
    assert dc["status"]["code"] == "not_logged_in" and dc["status"]["label"] == "未登录"
    assert card(d, "build")["status"]["label"] == "可用" and card(d, "build")["fallback"] is None
    txt = loop.ok("team").stdout
    assert "■ 验收  claude" in txt and "职责：换模型从头核对" in txt


def test_health_cached_five_minutes(loop):
    loop.http_responses({"/v1/models": [mag("a"), mag("a", "b"), mag("a", "b")]})
    team(loop); team(loop)
    assert len(magpie_probes(loop)) == 1                                   # 5 分钟内只问一次
    loop.env["EVO_NOW"] = "2026-10-20T12:06:00+08:00"
    assert team(loop)["magpie"]["models"] == ["a", "b"] and len(magpie_probes(loop)) == 2
    loop.ok("team", "--json", "--refresh")
    assert len(magpie_probes(loop)) == 3                                   # --refresh 强制


# ---------- 额度满 → 切备用 → 到点切回 ----------
def terms(loop):
    return [t["cmd"] for t in loop.orca_state()["terminals"].values() if t.get("cmd")]


def test_rate_limit_switches_to_fallback_then_back(loop):
    loop.project("AB")
    fallback_build(loop)
    loop.plan(build=["ratelimit"])
    loop.add("AB")
    loop.tick("AB"); loop.tick("AB")                                       # 主模型额度满 → 记暂停，这件原样重排
    rl = json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]
    assert "build" in rl and rl["build"]["account"] == "primary"
    assert not loop.telegram_sent()                                        # 有备用：不推「额度暂停」
    ev = [e for e in loop.outbox() if e["kind"] == "fallback_on"]
    assert len(ev) == 1 and "已切到备用 backup" in ev[0]["title"] and "自动切回" in ev[0]["body"]
    assert "rate_limited" not in kinds(loop)
    loop.run_until("AB", lambda s: s["items"][K]["state"] in ("built", "verifying", "verified", "merged"))
    it = loop.item("AB", K)
    assert it["dispatch"]["build"]["fallback"] and it["dispatch"]["build"]["model"] == "fb-model"
    assert any("--fb fb-model" in c for c in terms(loop))
    tlog = [json.loads(l) for l in open(os.path.join(loop.projects, "AB", "state", "timeline.jsonl"))]
    assert any(r["event"] == "fallback_on" and r["role"] == "build" for r in tlog)
    assert any(r["event"] == "dispatch" and r.get("fallback") and r.get("account") == "backup" for r in tlog)
    s = loop.status_json("AB")
    b = next(r for r in s["roles"] if r["role"] == "build")
    assert b["status"] != "rate_limited" and b["fallback"] is True
    assert next(c for c in s["team"]["cards"] if c["role"] == "build")["label"] == "用备用中"
    # 到点：切回主模型
    loop.env["EVO_NOW"] = "2026-10-20T17:01:00+08:00"
    loop.run_until("AB", state_is("merged", K))
    loop.add("AB", "修复登录页按钮错位", "api/")
    loop.run_until("AB", lambda s: s["items"]["AB-FIX-002"]["state"] not in ("queued",))
    assert loop.item("AB", "AB-FIX-002")["dispatch"]["build"]["fallback"] is False
    assert "fallback_off" in kinds(loop)


def test_fallback_does_not_interrupt_running_work(loop):
    loop.write_global({"limits": {"builders_total": 2, "stall_minutes": 999}})
    loop.project("AB")
    fallback_build(loop)
    loop.plan(build=["silent", "ratelimit"])
    loop.add("AB", "修复注册页验证码不刷新", "web/")
    loop.add("AB", "修复登录页按钮错位", "api/")
    loop.tick("AB"); loop.tick("AB")
    a = loop.item("AB", K)
    assert a["state"] == "building" and not a["dispatch"]["build"]["fallback"]          # 正在跑的那件不动
    loop.tick("AB")
    b = loop.item("AB", "AB-FIX-002")
    assert b["dispatch"]["build"]["fallback"] and loop.item("AB", K)["dispatch"]["build"]["id"] == a["dispatch"]["build"]["id"]


def test_fallback_at_night_goes_to_morning_digest(loop):
    loop.env["EVO_NOW"] = "2026-10-20T02:00:00+08:00"
    loop.project("AB")
    fallback_build(loop)
    loop.plan(build=["ratelimit"])
    loop.add("AB")
    loop.tick("AB"); loop.tick("AB")
    held = open(os.path.join(loop.root, "held.jsonl")).read()
    assert "fallback_on" in held and not loop.telegram_sent()
    loop.env["EVO_NOW"] = "2026-10-20T08:31:00+08:00"
    loop.ok("-p", "AB", "once")
    sent = loop.telegram_sent()
    assert sent and "早间汇总" in sent[-1]["text"] and "切到备用" in sent[-1]["text"]


def test_fallback_exhausted_too_pauses_and_pushes(loop):
    loop.project("AB")
    fallback_build(loop)
    loop.plan(build=["ratelimit", "ratelimit"])
    loop.add("AB")
    for _ in range(4):
        loop.tick("AB")
    rl = json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]
    assert "build" in rl and "build:fallback" in rl and rl["build:fallback"]["account"] == "backup"
    assert loop.item("AB")["state"] == "queued" and loop.status_json("AB")["items"][0]["waiting"] == "rate_limit"
    assert any("build:fallback" in m["text"] for m in loop.telegram_sent())          # 两个都满才推


# ---------- 停岗位：模型下线 / 不认识、撞模型、magpie 不通 ----------
def test_unknown_or_retired_model_blocks_dispatch_with_fix(loop):
    loop.project("AB")
    roles(loop, build={"models": ["group/evo-build"]})
    loop.http_responses({"/v1/models": [mag("glm")] * 3})
    loop.add("AB")
    loop.tick("AB"); loop.tick("AB")
    it = loop.item("AB")
    assert it["state"] == "queued" and it["waiting"] == "model_blocked" and "不在 magpie" in it["model_block"]
    assert not [w for w in loop.workers() if w["role"] == "build"]
    s = loop.status_json("AB")
    assert s["items"][0]["state"] == "等换模型" and s["team"]["blocked"]["build"]
    pushed = [m for m in loop.telegram_sent() if "施工岗停了" in m["text"]]
    assert len(pushed) == 1 and "evo team set build --model" in pushed[0]["text"]      # 只推一次，带改法
    roles(loop, build={"models": ["glm"]})                                             # 换了 → 下一轮就派
    loop.run_until("AB", lambda s: s["items"][K]["state"] != "queued")
    assert loop.item("AB")["dispatch"]["build"]["model"] == "glm"


def test_model_marked_retired_or_gone(loop):
    loop.project("AB")
    roles(loop, build={"models": ["glm"], "via": "magpie"})
    loop.http_responses({"/v1/models": [mag("glm", "ds"), mag("ds")]})
    team(loop)                                                                          # 第一次见到 glm
    loop.env["EVO_NOW"] = "2026-10-20T12:06:00+08:00"
    loop.add("AB")
    loop.tick("AB")
    it = loop.item("AB")
    assert it["waiting"] == "model_blocked" and "已从 magpie 下线" in it["model_block"]
    assert "model_gone" in kinds(loop)
    assert TEAM.model_problem("x", {"via": "magpie"}, {"magpie": {"ok": True, "models": [{"id": "x", "retired": True}]}}, {})[0] == "retired"


def test_verify_blocked_when_group_members_overlap(loop):
    loop.project("AB")
    roles(loop, build={"models": ["group/evo-build"]}, verify={"models": ["group/evo-verify"]})
    loop.http_responses({"/v1/models": [mag(extra=[{"id": "group/evo-build", "members": ["glm", "ds"]},
                                                   {"id": "group/evo-verify", "members": ["ds", "claude"]}])] * 3})
    loop.add("AB")
    loop.run_until("AB", lambda s: s["items"][K].get("waiting") == "model_blocked")
    it = loop.item("AB")
    assert it["state"] == "built" and "撞了" in it["model_block"]
    assert not [w for w in loop.workers() if w["role"] == "verify"]
    d = team(loop, "-p", "AB")
    assert any("重叠（ds）" in w for w in card(d, "verify")["warnings"])


def test_magpie_down_pauses_magpie_cards_cli_cards_keep_running(loop):
    loop.project("AB")
    roles(loop, build={"models": ["model-a"], "via": "cli"}, verify={"models": ["group/evo-verify"]})
    loop.http_responses({"/v1/models": [mag("group/evo-verify")]})
    team(loop)                                                                          # magpie 通
    loop.env["EVO_NOW"] = "2026-10-20T12:06:00+08:00"                    # 5 分钟后再问：不通
    loop.add("AB")
    loop.run_until("AB", lambda s: s["items"][K].get("waiting") == "magpie_down")
    assert loop.item("AB")["state"] == "built"                                         # 施工（工具自带模型）照跑
    assert [m for m in loop.telegram_sent() if "magpie 不通" in m["text"]]              # 整机推一次
    assert not [m for m in loop.telegram_sent() if "验收岗停了" in m["text"]]           # 不重复推
    assert loop.status_json("AB")["items"][0]["state"] == "等 magpie"
    roles(loop, verify={"fallback": {"tool": "claude2", "cmd": f"{PY} {WORKER} verify", "models": ["cli-v"], "via": "cli"}})
    loop.run_until("AB", state_is("merged", K))                                          # 配了工具自带的备用 → 用备用验收
    assert loop.item("AB")["dispatch"]["verify"]["fallback"] is True


# ---------- 新模型 ----------
def test_new_model_suggestion_once_and_dismiss(loop):
    loop.http_responses({"/v1/models": [mag("a"), mag("a", "b"), mag("a", "b")]})
    team(loop)
    assert "model_new" not in kinds(loop)                                              # 第一次只记下
    loop.env["EVO_NOW"] = "2026-10-20T12:06:00+08:00"
    d = team(loop)
    assert [x["model"] for x in d["suggestions"]] == ["b"]
    ev = [e for e in loop.outbox() if e["kind"] == "model_new"]
    assert len(ev) == 1 and "b" in ev[0]["body"] and "team trial" in ev[0]["body"]
    loop.env["EVO_NOW"] = "2026-10-20T12:12:00+08:00"
    team(loop)
    assert len([e for e in loop.outbox() if e["kind"] == "model_new"]) == 1
    loop.ok("team", "dismiss", "b")
    assert team(loop)["suggestions"] == []


# ---------- 换模型：evo team set / clear / trial ----------
def test_team_set_global_and_project_with_badges(loop):
    loop.project("AB")
    r = loop.evo("team", "set", "verify", "--model", "model-b")
    assert r.returncode != 0 and "施工和验收不能用同一个模型" in r.stderr               # 施工列表里也有 model-b
    roles(loop, build={"models": ["model-a"]})
    loop.ok("team", "set", "verify", "--model", "model-b", "--thinking", "high", "--duty", "核对证据")
    v = gcfg(loop)["roles"]["verify"]
    assert v["models"] == ["model-b"] and v["thinking"] == "high" and v["duty"] == "核对证据"
    assert v["prompt"] == "roles/verifier.md"                                            # 其他键不动
    out = loop.ok("team", "set", "build", "--model", "model-c", "--project", "AB").stdout
    assert "AB 本项目专用" in out and "下一次派工生效" in out
    assert json.load(open(loop.cfg_path("AB")))["overrides"]["roles"]["build"]["models"] == ["model-c"]
    d = team(loop, "-p", "AB")
    assert card(d, "build")["badge"] == "本项目专用" and card(d, "verify")["badge"] == "跟随全局"
    assert card(d, "build")["models"] == ["model-c"]
    assert team(loop)["projects"][0]["overrides"]["build"]["models"] == ["model-c"]
    loop.add("AB"); loop.tick("AB")
    assert loop.item("AB")["dispatch"]["build"]["model"] == "model-c"                   # 下一次派工就用
    loop.ok("team", "clear", "build", "--project", "AB")
    assert "overrides" not in json.load(open(loop.cfg_path("AB")))
    for bad in (["--model", "x;rm -rf /"], ["--thinking", "huge"], ["--tool", "Bad Tool"]):
        assert loop.evo("team", "set", "build", *bad).returncode != 0
    assert loop.evo("team", "set", "boss", "--model", "x").returncode != 0


def test_team_set_rejects_unknown_magpie_model_and_tool_template(loop):
    roles(loop, build={"models": ["group/evo-build"]})
    loop.http_responses({"/v1/models": [mag("group/evo-build", "group/evo-verify")]})
    r = loop.evo("team", "set", "build", "--model", "group/evo-buidl")
    assert r.returncode != 0 and "不在 magpie" in r.stderr
    loop.ok("team", "set", "decide", "--tool", "codex", "--thinking", "high")
    d = gcfg(loop)["roles"]["decide"]
    assert d["cmd"] == TEAM.TOOL_CMDS["codex"] and d["tool"] == "codex" and d["thinking"] == "high"
    loop.ok("team", "set", "build", "--fallback-tool", "dsh", "--fallback-model", "group/evo-verify")
    fb = gcfg(loop)["roles"]["build"]["fallback"]
    assert fb == {"tool": "dsh", "cmd": TEAM.TOOL_CMDS["dsh"], "models": ["group/evo-verify"], "via": "magpie"}
    loop.ok("team", "set", "build", "--no-fallback")
    assert "fallback" not in gcfg(loop)["roles"]["build"]


def test_thinking_level_reaches_worker_command(loop):
    loop.project("AB")
    roles(loop, build={"cmd": f"{PY} {WORKER} build --model {{model}} --think {{thinking}}", "models": ["model-a"], "thinking": "high"},
          verify={"models": ["model-b"]})
    loop.add("AB"); loop.tick("AB")
    assert any(c.endswith("build --model model-a --think high") for c in terms(loop))


def test_agents_can_never_change_models(loop):
    loop.project("AB")
    loop.env["EVO_AGENT"] = "muse"
    for args in (["set", "build", "--model", "model-b"], ["clear", "build", "--project", "AB"],
                 ["trial", "build", "model-b", "--project", "AB"], ["init", "--apply"], ["dismiss", "x"]):
        r = loop.evo("team", *args)
        assert r.returncode != 0 and "外部 Agent" in r.stderr, args
    assert loop.evo("team", "--json").returncode == 0                                   # 看可以
    loop.env.pop("EVO_AGENT")
    assert gcfg(loop)["roles"]["build"]["models"] == ["model-a", "model-b"]


def test_trial_on_one_project_reports_comparison_once(loop):
    loop.project("AB")
    roles(loop, verify={"models": ["model-b"]}, build={"models": ["model-a"]})
    loop.ok("team", "trial", "build", "model-c", "--project", "AB", "--items", "1")
    o = json.load(open(loop.cfg_path("AB")))["overrides"]["roles"]["build"]
    assert o["models"] == ["model-c"] and o["trial"]["base"] == ["model-a"] and o["trial"]["items"] == 1
    d = team(loop, "-p", "AB")
    assert card(d, "build")["trial"]["model"] == "model-c" and card(d, "build")["trial"]["done"] == 0
    loop.add("AB")
    loop.run_until("AB", state_is("merged", K))
    loop.tick("AB"); loop.tick("AB")
    ev = [e for e in loop.outbox() if e["kind"] == "trial_done"]
    assert len(ev) == 1 and "model-c" in ev[0]["title"] and "--project AB" in ev[0]["body"]
    assert card(team(loop, "-p", "AB"), "build")["trial"]["done"] == 1
    loop.ok("team", "set", "build", "--model", "model-c", "--project", "AB")              # 留用：试用标记去掉
    assert "trial" not in json.load(open(loop.cfg_path("AB")))["overrides"]["roles"]["build"]


def test_card_stats_and_usage_from_real_runs(loop):
    loop.project("AB")
    roles(loop, build={"models": ["model-a"]}, verify={"models": ["model-b"]})
    loop.plan(verify=["fail", "pass"])
    loop.add("AB")
    loop.run_until("AB", state_is("merged", K), n=12)
    d = team(loop, "-p", "AB")
    b = card(d, "build")
    assert b["stats"]["model-a"]["items"] == 1 and b["stats"]["model-a"]["verify_reject_rate"] == 0.5
    assert b["stats"]["model-a"]["rework_per_item"] == 1.0
    assert card(d, "verify")["stats"]["model-b"]["rejects"] == 1
    assert "数据还少" in b["recommendation"]["text"] and b["recommendation"]["switch_to"] is None
    acct = b["account"]
    assert d["usage_week"][acct]["runs"] >= 4 and b["usage_week"]["runs"] >= 4


# ---------- 首次安装向导 ----------
def test_init_wizard_proposes_and_applies_cards(loop):
    fake_cli(loop, "claude", "codex", "dsh")
    loop.http_responses({"/v1/models": [mag("group/evo-build", "group/evo-verify", "glm")] * 2})
    p = json.loads(loop.ok("team", "init", "--json").stdout)
    c = p["cards"]
    assert c["build"]["tool"] == "dsh" and c["build"]["models"] == ["group/evo-build"] and c["build"]["fallback"]["tool"] == "codex"
    assert c["verify"]["tool"] == "claude" and c["verify"]["fallback"]["models"] == ["group/evo-verify"]
    assert c["decide"]["thinking"] == "high" and p["magpie"]["groups"] == ["group/evo-build", "group/evo-verify"]
    assert "build" in gcfg(loop)["roles"] and gcfg(loop)["roles"]["build"].get("tool") is None     # 只看不写
    loop.ok("team", "init", "--apply")
    g = gcfg(loop)["roles"]
    assert g["build"]["tool"] == "dsh" and g["build"]["prompt"] == "roles/builder.md" and g["decide"]["tool"] == "claude"
    assert g["verify"]["duty"]


def test_init_wizard_without_magpie_notes_it(loop):
    fake_cli(loop, "claude")
    p = json.loads(loop.ok("team", "init", "--json").stdout)
    assert "build" not in p["cards"] and any("magpie 没响应" in n for n in p["notes"])


# ---------- 面板 ----------
def test_panel_team_endpoints(loop):
    loop.project("AB")
    roles(loop, build={"models": ["model-a"]})
    loop.env["EVO_PANEL_KEYCHAIN"] = "0"
    p, base, token = start_panel(loop, loop.env)
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        assert req(base + "/api/team")[0] == 401
        assert req(base + "/api/team", json.dumps({"role": "verify", "model": "x"}).encode(), {"Content-Type": "application/json"})[0] == 401
        code, _, body = req(base + "/api/team?code=AB", headers=auth)
        assert code == 200 and card(json.loads(body), "build")["badge"] == "跟随全局"
        code, _, body = req(base + "/api/team", json.dumps({"action": "set", "role": "verify", "model": "model-b", "thinking": "high"}).encode(), auth)
        assert code == 410 and "evo" in json.loads(body)["error"]          # 第二十五轮（#12）：面板只读，换模型用 evo team set
        assert "verify" not in (gcfg(loop).get("roles") or {}) or gcfg(loop)["roles"]["verify"].get("models") != ["model-b"]
    finally:
        p.terminate(); p.wait(5)


def test_status_json_team_is_additive(loop):
    loop.project("AB")
    s = loop.status_json("AB")
    assert s["schema_version"] == 1 and {c["role"] for c in s["team"]["cards"]} == {"build", "verify", "decide"}
    assert s["team"]["magpie_ok"] is False and s["team"]["blocked"] == {}
    assert all("fallback" in r for r in s["roles"])
