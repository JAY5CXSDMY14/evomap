"""第二十一轮补：额度账号分开算。

以前「账号」默认取命令的第一个词：原生 Pro 的决策岗（claude …）和走 magpie 的 claude 验收岗都算 `claude`，
Pro 满了两个一起停；命令用 `env VAR=… claude` 包一层，账号就成了 `env`。
现在：显式 account → 显式 tool → 命令里真正跑的程序（跳过 env、env 的选项和 KEY=VAL）。
evo team set 新增 --account / --fallback-account / --cmd，老板不用手改 roles.decide.cmd。
"""
import json, os, sys

from conftest import KIT, WORKER

sys.path.insert(0, os.path.join(KIT, "bin"))
sys.path.insert(0, os.path.join(KIT, "features", "team"))
import evo_roles as R      # noqa: E402
import evo_team as TEAM    # noqa: E402

PY = sys.executable
K = "AB-FIX-001"


# ---------- 纯逻辑 ----------
def test_cmd_tool_skips_env_and_assignments():
    assert R.cmd_tool("claude -p --model {model}") == "claude"
    assert R.cmd_tool("env CLAUDE_CONFIG_DIR=~/.claude-pro claude -p") == "claude"
    assert R.cmd_tool("CLAUDE_CONFIG_DIR=/x DISABLE_AUTOUPDATER=1 claude") == "claude"
    assert R.cmd_tool("env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY CLAUDE_CONFIG_DIR=/x claude -p") == "claude"
    assert R.cmd_tool("/usr/bin/env -i PATH=/usr/bin /opt/bin/codex exec") == "codex"
    assert R.cmd_tool("env --unset=FOO dsh-tui .") == "dsh-tui"
    assert R.cmd_tool("env") == "" and R.cmd_tool("A=1") == "" and R.cmd_tool("") == "" and R.cmd_tool("'bad") == ""


def test_account_precedence_account_then_tool_then_cmd():
    pro = "env -u ANTHROPIC_BASE_URL CLAUDE_CONFIG_DIR=/x claude -p"
    assert R.account_of({"cmd": pro}) == "claude" and R.tool_of({"cmd": pro}) == "claude"   # 以前是 env
    assert R.account_of({"cmd": pro, "tool": "claude"}) == "claude"
    assert R.account_of({"cmd": pro, "tool": "claude", "account": "claude-pro"}) == "claude-pro"
    assert R.tool_of({"cmd": pro, "account": "claude-pro"}) == "claude"                    # account 不改工具
    assert R.account_of({"cmd": "codex --model x"}) == "codex"                             # 老配置不变
    assert R.account_of({}) == "?"
    fb = R.fallback_rc({"cmd": pro, "tool": "claude", "account": "claude-pro",
                        "fallback": {"tool": "claude", "models": ["group/evo-verify"], "account": "magpie"}})
    assert R.account_of(fb) == "magpie" and fb["cmd"] == R.TOOL_CMDS["claude"]             # 备用不继承 Pro 命令
    fb2 = R.fallback_rc({"cmd": pro, "account": "claude-pro", "fallback": {"tool": "claude", "models": ["m"]}})
    assert R.account_of(fb2) == "claude"                                                   # 备用不继承主卡的 account


# ---------- 额度暂停按账号 ----------
def deciders(loop, decide, verify=None):
    g = {"roles": {"decide": {"prompt": "roles/decider.md", "boot_seconds": 0, "models": ["model-x"], **decide}},
         "limits": {"rework_rounds": 0, "decide_every_minutes": 0}}
    if verify:
        g["roles"]["verify"] = {"cmd": f"{PY} {WORKER} verify", "models": ["model-a", "model-b"], "prompt": "roles/verifier.md",
                                "boot_seconds": 0, **verify}
    loop.write_global(g)


def rl_roles(loop):
    p = os.path.join(loop.root, "ratelimit.json")
    return json.load(open(p))["roles"] if os.path.exists(p) else {}


def escalate(loop, decide_moves):
    loop.project("AB")
    loop.plan(verify=["fail"], decide=decide_moves)
    loop.add("AB")


def test_env_wrapped_decider_without_account_still_shares_like_before(loop):
    """没写 account：账号按真正跑的程序算（这里所有岗位都是 python），和以前一样一起停——只是不再叫 env。"""
    deciders(loop, {"cmd": f"env EVO_FAKE=1 {PY} {WORKER} decide"})
    escalate(loop, ["ratelimit"])
    loop.run_until("AB", lambda s: "decide" in rl_roles(loop), n=10)
    rl = rl_roles(loop)
    acct = os.path.basename(PY)
    assert rl["decide"]["account"] == acct
    assert {"build", "verify", "decide"} <= set(rl)                                       # 同账号一起停（老行为）


def test_pro_decider_pauses_alone(loop):
    deciders(loop, {"cmd": f"env EVO_FAKE=1 {PY} {WORKER} decide", "tool": "claude", "account": "claude-pro"},
             verify={"tool": "claude", "account": "magpie"})
    escalate(loop, ["ratelimit"])
    loop.run_until("AB", lambda s: "decide" in rl_roles(loop), n=10)
    rl = rl_roles(loop)
    assert set(rl) == {"decide"} and rl["decide"]["account"] == "claude-pro"              # 验收、施工照常
    sent = loop.telegram_sent()
    assert any("decide" in m["text"] and "verify" not in m["text"] for m in sent)
    st = loop.status_json("AB")
    assert {r["role"]: r["status"] for r in st["roles"]}["verify"] != "rate_limited"
    assert [(x["role"], x["account"]) for x in st["rate_limits"]] == [("decide", "claude-pro")]


def test_magpie_verifier_limit_does_not_pause_pro_decider(loop):
    deciders(loop, {"cmd": f"{PY} {WORKER} decide", "tool": "claude", "account": "claude-pro"},
             verify={"tool": "claude", "account": "magpie"})
    loop.project("AB")
    loop.plan(verify=["ratelimit"])
    loop.add("AB")
    loop.run_until("AB", lambda s: "verify" in rl_roles(loop), n=10)
    rl = rl_roles(loop)
    assert "decide" not in rl and rl["verify"]["account"] == "magpie"


def test_pro_decider_limit_switches_to_magpie_fallback(loop):
    deciders(loop, {"cmd": f"{PY} {WORKER} decide --pro", "tool": "claude", "account": "claude-pro",
                    "fallback": {"cmd": f"{PY} {WORKER} decide --fb {{model}}", "tool": "claude", "account": "magpie",
                                 "models": ["fb-model"]}},
             verify={"tool": "claude", "account": "magpie"})
    escalate(loop, ["ratelimit", {"decisions": [{"item": K, "action": "drop", "note": "不做了"}]}])
    loop.run_until("AB", lambda s: any("决策岗批次做完" in l for l in s["log"]), n=12)
    rl = rl_roles(loop)
    assert set(rl) == {"decide"} and rl["decide"]["account"] == "claude-pro"
    assert not any("decide" in m["text"] and "暂停" in m["text"] for m in loop.telegram_sent())   # 有备用：不推暂停
    ev = [e for e in loop.outbox() if e["kind"] == "fallback_on"]
    assert len(ev) == 1 and "决策岗额度满" in ev[0]["title"] and "claude-pro" in ev[0]["body"]
    dec = loop.state("AB")["decide"]
    assert dec["fallback"] is True
    cmds = [t["cmd"] for t in loop.orca_state()["terminals"].values() if t.get("cmd")]
    assert any("--fb fb-model" in c for c in cmds) and sum("--pro" in c for c in cmds) == 1    # 重置前不再碰 Pro


# ---------- evo team set --account / --cmd / --fallback-account ----------
def gcfg(loop):
    return json.load(open(os.path.join(loop.root, "config.json")))


def test_team_set_account_cmd_and_fallback_account(loop):
    loop.project("AB")
    pro = "env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY CLAUDE_CONFIG_DIR=$HOME/.claude-pro claude -p --model {model}"
    out = loop.ok("team", "set", "decide", "--tool", "claude", "--cmd", pro, "--account", "claude-pro").stdout
    assert "额度账号 claude-pro" in out
    d = gcfg(loop)["roles"]["decide"]
    assert d["cmd"] == pro and d["tool"] == "claude" and d["account"] == "claude-pro"
    loop.ok("team", "set", "decide", "--fallback-tool", "claude", "--fallback-model", "fb-model", "--fallback-account", "magpie")
    fb = gcfg(loop)["roles"]["decide"]["fallback"]
    assert fb["account"] == "magpie" and fb["cmd"] == TEAM.TOOL_CMDS["claude"] and fb["models"] == ["fb-model"]
    doc = json.loads(loop.ok("team", "--json").stdout)
    c = next(c for c in doc["cards"] if c["role"] == "decide")
    assert c["account"] == "claude-pro" and c["fallback"]["account"] == "magpie" and c["tool"] == "claude"
    assert "账号 claude-pro" in loop.ok("team").stdout
    loop.ok("team", "set", "decide", "--account", "auto")
    assert "account" not in gcfg(loop)["roles"]["decide"]
    for bad in (["--account", "Claude Pro"], ["--account", "a;b"], ["--fallback-account", "X"],
                ["--cmd", ""], ["--cmd", "env A=1"], ["--cmd", "claude\nrm -rf /"]):
        r = loop.evo("team", "set", "decide", *bad)
        assert r.returncode != 0, bad
    assert gcfg(loop)["roles"]["decide"]["cmd"] == pro
