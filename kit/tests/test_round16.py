"""第十六轮：App ↔ evo 的 JSON 接口定版本（schema_version + kit/schemas/ 校验）+ 插件机制（evo plugin …、通知渠道）。"""
import json, os, shutil, sys

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from conftest import KIT, state_is

SCHEMAS = os.path.join(KIT, "schemas")
EXAMPLE = os.path.join(KIT, "plugins", "example-hello")
sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_plugin as PLUG  # noqa: E402


def _registry():
    res = []
    for f in os.listdir(SCHEMAS):
        d = json.load(open(os.path.join(SCHEMAS, f), encoding="utf-8"))
        res.append((d["$id"], Resource.from_contents(d)))
    return Registry().with_resources(res)


REG = _registry()


def check(schema, doc):
    s = json.load(open(os.path.join(SCHEMAS, schema), encoding="utf-8"))
    v = Draft202012Validator(s, registry=REG)
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    assert not errs, f"{schema}: " + "; ".join(f"{list(e.path)} {e.message}" for e in errs[:5])
    return doc


def js(r):
    return json.loads(r.stdout)


def plugins_root(loop):
    return os.path.join(loop.root, "plugins")


def make_plugin(loop, name, script, contributes=None, **extra):
    """在插件目录里造一个插件：script 是 python 源码，run 都指向它。"""
    d = os.path.join(plugins_root(loop), name)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "p.py"), "w", encoding="utf-8").write(script)
    m = {"name": name, "version": "1.0.0", "evo_api": "^1", "enabled": True,
         "contributes": contributes or {"sidebar_pages": [{"id": "main", "title": "主页", "run": ["python3", "p.py"]}]}, **extra}
    json.dump(m, open(os.path.join(d, "plugin.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return d


CARD_OK = 'import json,sys; sys.stdin.read(); print(json.dumps({"schema_version":1,"title":"t","blocks":[{"type":"text","text":"x"}]}))\n'


# ---------- 一、接口定版本 ----------

def test_all_schemas_are_valid_draft2020():
    for f in os.listdir(SCHEMAS):
        d = json.load(open(os.path.join(SCHEMAS, f), encoding="utf-8"))
        Draft202012Validator.check_schema(d)
        assert d["$id"].endswith(f)


def test_app_json_outputs_match_schemas(loop):
    """App 调的每个 --json：顶层 schema_version=1，且符合 kit/schemas/。"""
    loop.project("AB")
    loop.add("AB")
    loop.run_until("AB", state_is("merged"))
    pj = check("projects.schema.json", js(loop.ok("projects", "--json")))
    assert pj["schema_version"] == 1 and [p["code"] for p in pj["projects"]] == ["AB"]
    assert pj["projects"][0]["name"] == "项目AB"
    st = check("status.schema.json", loop.status_json("AB"))
    assert st["schema_version"] == 1
    key = st["items"][0]["key"]
    lg = check("log.schema.json", js(loop.ok("-p", "AB", "log", key, "--json")))
    assert lg["schema_version"] == 1 and lg["events"]
    tm = check("team.schema.json", js(loop.ok("team", "--json")))
    assert tm["schema_version"] == 1
    ti = check("team-init.schema.json", js(loop.ok("team", "init", "--json")))
    assert ti["schema_version"] == 1
    pl = check("plugin-list.schema.json", js(loop.ok("plugin", "list", "--json")))
    assert pl["schema_version"] == 1 and pl["plugins"] == []


def test_other_json_outputs_carry_schema_version(loop):
    loop.project("AB")
    assert js(loop.ok("models", "--json"))["schema_version"] == 1
    assert js(loop.ok("-p", "AB", "ui", "show", "--json"))["schema_version"] == 1
    assert js(loop.ok("-p", "AB", "arch", "show", "--json"))["schema_version"] == 1


def test_projects_text_output_unchanged(loop):
    """老 App（和 ProjectList.parse）还读纯文本：不带 --json 的输出不变。"""
    loop.project("AB")
    out = loop.ok("projects").stdout
    assert out.split()[0] == "AB" and not out.lstrip().startswith("{")


# ---------- 二、插件：发现、开关、校验 ----------

def test_install_defaults_to_disabled_and_enable_runs(loop):
    r = loop.ok("plugin", "install", EXAMPLE)
    assert "默认关着" in r.stdout
    pl = check("plugin-list.schema.json", js(loop.ok("plugin", "list", "--json")))
    p = pl["plugins"][0]
    assert p["name"] == "example-hello" and p["valid"] and p["compatible"] and not p["enabled"] and not p["active"]
    c = p["contributes"]
    assert [x["id"] for x in c["sidebar_pages"]] == ["hello"]
    assert [x["name"] for x in c["composer_commands"]] == ["hello"]
    assert [x["id"] for x in c["notify_channels"]] == ["hello-log"]
    assert [x["id"] for x in c["item_actions"]] == ["hello-item"]
    assert "run" not in json.dumps(c)                     # 命令行不给 App
    # 关着时跑不了：信封 ok=false、退出码 3
    r = loop.evo("plugin", "run", "example-hello", "sidebar_page", "hello", "--json")
    assert r.returncode == 3
    env = check("plugin-run.schema.json", js(r))
    assert not env["ok"] and "还没打开" in env["error"]
    loop.ok("plugin", "enable", "example-hello")
    assert js(loop.ok("plugin", "list", "--json"))["plugins"][0]["active"]
    env = check("plugin-run.schema.json", js(loop.ok("plugin", "run", "example-hello", "sidebar_page", "hello", "--json")))
    assert env["ok"] and env["card"]["title"].startswith("你好")
    types = [b["type"] for b in env["card"]["blocks"]]
    assert {"text", "list", "table", "buttons"} <= set(types)
    check("card.schema.json", env["card"])
    # 按钮 → 同一个命令，带 action / payload
    env = js(loop.ok("plugin", "run", "example-hello", "sidebar_page", "hello", "--action", "roll", "--payload", '{"sides":6}', "--json"))
    assert env["ok"] and "掷出了" in env["card"]["blocks"][0]["text"]
    # 输入框命令：按 name 找，参数原样给
    env = js(loop.ok("plugin", "run", "example-hello", "composer_command", "hello", "--args", "小陶", "--project", "AB", "--json"))
    assert env["ok"] and env["card"]["title"] == "你好，小陶！" and "AB" in env["card"]["blocks"][0]["text"]
    env = js(loop.ok("plugin", "run", "example-hello", "item_action", "hello-item", "--project", "AB", "--item", "AB-FIX-001", "--json"))
    assert env["ok"] and "AB-FIX-001" in env["card"]["title"]
    loop.ok("plugin", "disable", "example-hello")
    assert not js(loop.ok("plugin", "list", "--json"))["plugins"][0]["enabled"]


def test_install_refuses_overwrite_without_force(loop):
    loop.ok("plugin", "install", EXAMPLE)
    loop.ok("plugin", "enable", "example-hello")
    r = loop.evo("plugin", "install", EXAMPLE)
    assert r.returncode != 0 and "--force" in r.stderr
    loop.ok("plugin", "install", EXAMPLE, "--force")
    assert not js(loop.ok("plugin", "list", "--json"))["plugins"][0]["enabled"]   # 重装回到关着


def test_external_agent_cannot_toggle_or_install(loop):
    loop.ok("plugin", "install", EXAMPLE)
    loop.env["EVO_AGENT"] = "muse"
    for args in (("enable", "example-hello"), ("disable", "example-hello"), ("install", EXAMPLE, "--force")):
        r = loop.evo("plugin", *args)
        assert r.returncode != 0 and "外部 Agent" in (r.stderr + r.stdout)
    assert loop.evo("plugin", "list", "--json").returncode == 0                          # 看可以


def test_example_manifest_matches_schema_and_validate_ok(loop):
    check("plugin-manifest.schema.json", json.load(open(os.path.join(EXAMPLE, "plugin.json"), encoding="utf-8")))
    r = loop.ok("plugin", "validate", EXAMPLE, "--json")
    assert js(r)["ok"]


def test_validate_reports_bad_manifest(loop):
    d = make_plugin(loop, "bad-one", CARD_OK, contributes={
        "sidebar_pages": [{"id": "Main", "title": "x", "run": "p.py"}],
        "composer_commands": [{"id": "c", "name": "help", "title": "x", "run": ["p.py"]}],
        "toolbar": []})
    raw = json.load(open(os.path.join(d, "plugin.json")))
    raw["name"] = "other-name"
    json.dump(raw, open(os.path.join(d, "plugin.json"), "w"))
    r = loop.evo("plugin", "validate", "bad-one", "--json")
    assert r.returncode == 1
    errs = " ".join(js(r)["plugins"][0]["errors"])
    for w in ("文件夹名", "id 只能是", "run 要是", "保留词", "toolbar"):
        assert w in errs, errs
    p = js(loop.ok("plugin", "list", "--json"))["plugins"][0]
    assert not p["valid"] and not p["active"]


def test_incompatible_evo_api_is_listed_but_not_run(loop):
    make_plugin(loop, "future", CARD_OK, evo_api=">=2")
    p = js(loop.ok("plugin", "list", "--json"))["plugins"][0]
    assert p["valid"] and not p["compatible"] and not p["active"]
    env = js(loop.evo("plugin", "run", "future", "sidebar_page", "main", "--json"))
    assert not env["ok"] and "不兼容" in env["error"]


def test_api_range_syntax():
    assert PLUG.api_matches("^1") and PLUG.api_matches("1") and PLUG.api_matches(">=1 <2") and PLUG.api_matches(">=1.0,<3")
    assert PLUG.api_matches("*") and PLUG.api_matches("~1.0")
    assert not PLUG.api_matches("^2") and not PLUG.api_matches(">1") and not PLUG.api_matches("<1")
    with pytest.raises(ValueError):
        PLUG.api_matches("latest")


# ---------- 三、插件：子进程隔离（超时、输出上限、坏输出、环境白名单）----------

def test_timeout_kills_plugin(loop):
    make_plugin(loop, "slow", "import time; time.sleep(30)\n", timeout_seconds=1)
    r = loop.evo("plugin", "run", "slow", "sidebar_page", "main", "--json", timeout=20)
    env = js(r)
    assert r.returncode == 3 and not env["ok"] and "超时" in env["error"] and env["elapsed_ms"] < 10000


def test_output_cap(loop):
    make_plugin(loop, "chatty", "import sys; sys.stdout.write('x' * (400 * 1024)); sys.stdout.flush()\n")
    env = js(loop.evo("plugin", "run", "chatty", "sidebar_page", "main", "--json"))
    assert not env["ok"] and "256 KB" in env["error"]


def test_bad_outputs_are_errors_not_crashes(loop):
    make_plugin(loop, "notjson", "print('hello')\n")
    make_plugin(loop, "badcard", 'import json; print(json.dumps({"title": "", "blocks": [{"type": "video"}]}))\n')
    make_plugin(loop, "crash", "import sys; sys.stderr.write('炸了\\n'); sys.exit(7)\n")
    e1 = js(loop.evo("plugin", "run", "notjson", "sidebar_page", "main", "--json"))
    e2 = js(loop.evo("plugin", "run", "badcard", "sidebar_page", "main", "--json"))
    e3 = js(loop.evo("plugin", "run", "crash", "sidebar_page", "main", "--json"))
    assert "不是 JSON" in e1["error"]
    assert "缺 title" in e2["error"] and "video" in e2["error"]
    assert "退出码 7" in e3["error"] and "炸了" in e3["error"]
    for e in (e1, e2, e3):
        check("plugin-run.schema.json", e)


def test_plugin_env_is_whitelisted(loop):
    """插件拿不到任何密钥类环境变量（EVO_TG_TOKEN 等），只有白名单 + EVO_PLUGIN_*。"""
    make_plugin(loop, "envdump", 'import json, os, sys; sys.stdin.read(); print(json.dumps({"title": "env", "blocks": ['
                '{"type": "text", "text": json.dumps(sorted(os.environ))}]}))\n')
    loop.env["MY_SECRET_TOKEN"] = "s3cr3t"
    env = js(loop.ok("plugin", "run", "envdump", "sidebar_page", "main", "--json"))
    keys = set(json.loads(env["card"]["blocks"][0]["text"]))
    assert "EVO_TG_TOKEN" not in keys and "MY_SECRET_TOKEN" not in keys and "EVO_HOME" not in keys
    allowed = set(PLUG.ENV_ALLOW) | {"EVO_API", "EVO_PLUGIN_NAME", "EVO_PLUGIN_DIR", "EVO_PLUGIN_DATA", "PYTHONIOENCODING",
                                     "PYTHONDONTWRITEBYTECODE", "LC_CTYPE", "__CF_USER_TEXT_ENCODING"}
    assert keys <= allowed, keys - allowed
    assert {"EVO_PLUGIN_NAME", "EVO_PLUGIN_DATA", "EVO_API"} <= keys


def test_request_on_stdin(loop):
    make_plugin(loop, "echo", 'import json, sys; r = json.load(sys.stdin); print(json.dumps({"title": "echo", "blocks": ['
                '{"type": "text", "text": json.dumps(r, ensure_ascii=False)}]}))\n',
                contributes={"composer_commands": [{"id": "e", "name": "echo", "title": "回声", "run": ["python3", "p.py"]}]})
    env = js(loop.ok("plugin", "run", "echo", "composer_command", "echo", "--args", "a b", "--project", "AB", "--json"))
    req = json.loads(env["card"]["blocks"][0]["text"])
    assert req["kind"] == "composer_command" and req["id"] == "e" and req["args"] == "a b" and req["project"] == "AB"
    assert req["evo_api"] == "1.0" and req["plugin"] == "echo"


def test_card_validation_limits_and_truncation():
    c, errs = PLUG.validate_card({"title": "x" * 5000, "blocks": [{"type": "table", "columns": ["a", "b"], "rows": [["1"], [2, 3, 4]]}]})
    assert not errs and len(c["title"]) == PLUG.MAX_TEXT and c["blocks"][0]["rows"] == [["1", ""], ["2", "3"]]
    _, errs = PLUG.validate_card({"title": "x", "blocks": [{"type": "buttons", "buttons": [{"label": "b", "action": "a"}] * 7}]})
    assert any("最多 6" in e for e in errs)
    _, errs = PLUG.validate_card({"schema_version": 2, "title": "x", "blocks": []})
    assert any("schema_version" in e for e in errs)


# ---------- 四、通知渠道 ----------

NOTIFY_SCRIPT = ('import json, os, sys; r = json.load(sys.stdin)\n'
                 'open(os.path.join(os.environ["EVO_PLUGIN_DATA"], "got.jsonl"), "a").write(json.dumps(r["event"], ensure_ascii=False) + "\\n")\n')


def got(loop, name):
    p = os.path.join(loop.root, "plugin-data", name, "got.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def test_notify_channel_receives_push_events(loop):
    make_plugin(loop, "pushme", NOTIFY_SCRIPT, contributes={"notify_channels": [{"id": "log", "title": "记下来", "run": ["python3", "p.py"]}]})
    make_plugin(loop, "allme", NOTIFY_SCRIPT, contributes={"notify_channels": [{"id": "log", "title": "全收", "events": "all", "run": ["python3", "p.py"]}]})
    make_plugin(loop, "offme", NOTIFY_SCRIPT, enabled=False, contributes={"notify_channels": [{"id": "log", "title": "关着", "run": ["python3", "p.py"]}]})
    r = loop.ok("notify-test")
    assert "plugin:pushme/log" in r.stdout
    assert [e["kind"] for e in got(loop, "pushme")] == ["test"]
    assert got(loop, "offme") == []
    # 一个真的 push 事件：卡住（看门狗）；一个 info 事件：gate_created
    sys.path.insert(0, os.path.join(KIT, "bin"))
    code = (f"import os, sys; sys.path.insert(0, {os.path.join(KIT, 'bin')!r}); import evo_notify as N; "
            f"n = N.Notifier({{'notify': {{'quiet_hours': {{}}, 'channels': []}}}}, {loop.root!r}, 'AB'); "
            "n.emit('stalled', '疑似卡住', '工人没了', item='AB-FIX-001'); n.emit('gate_created', '新闸门', '')")
    import subprocess
    subprocess.run([sys.executable, "-c", code], env=loop.env, check=True, capture_output=True, text=True)
    assert [e["kind"] for e in got(loop, "pushme")] == ["test", "stalled"]
    assert [e["kind"] for e in got(loop, "allme")] == ["test", "stalled", "gate_created"]
    ev = got(loop, "pushme")[-1]
    assert ev["schema_version"] == 1 and ev["project"] == "AB" and ev["item"] == "AB-FIX-001"


def test_broken_notify_plugin_does_not_break_loop(loop):
    """插件通知渠道挂了：提醒照发（outbox 照写），接棒照转。"""
    make_plugin(loop, "broken", "import sys; sys.exit(1)\n",
                contributes={"notify_channels": [{"id": "x", "title": "坏的", "events": "all", "run": ["python3", "p.py"]}]})
    make_plugin(loop, "missing", "", contributes={"notify_channels": [{"id": "x", "title": "没有程序", "events": "all", "run": ["./nope"]}]})
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))               # 接棒照转，看效果闸门照建
    assert any(e["kind"] == "gate_created" for e in loop.outbox())   # 事件照写（插件渠道每次都失败）
    r = loop.evo("notify-test")                              # 有渠道失败：退出码 1，但每个渠道都报了
    assert "plugin:broken/x ✗" in r.stdout and "plugin:missing/x ✗" in r.stdout and "telegram  ✓" in r.stdout


def test_quiet_hours_hold_plugin_push(loop):
    """免打扰时段：要推的事攒着（插件渠道也不发），早间汇总时插件收到 digest_morning。"""
    make_plugin(loop, "pushme", NOTIFY_SCRIPT, contributes={"notify_channels": [{"id": "log", "title": "记下来", "run": ["python3", "p.py"]}]})
    code = (f"import sys; sys.path.insert(0, {os.path.join(KIT, 'bin')!r}); import evo_notify as N; "
            f"n = N.Notifier({{'notify': {{'quiet_hours': {{'start': '00:00', 'end': '23:59'}}, 'channels': []}}}}, {loop.root!r}, 'AB'); "
            "n.emit('stalled', '疑似卡住', '工人没了'); n.flush_digest(force=True)")
    import subprocess
    subprocess.run([sys.executable, "-c", code], env=loop.env, check=True, capture_output=True, text=True)
    assert [e["kind"] for e in got(loop, "pushme")] == ["digest_morning"]
