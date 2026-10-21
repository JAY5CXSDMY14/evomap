"""第十八轮：内核 + 功能包（照 magpie 插件运行时）、事件总线、evo watch、自维护基础、多机器。"""
import ast, glob, json, os, shutil, subprocess, sys, threading, time

import pytest

from conftest import KIT, EVO, state_is

sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_bus as BUS  # noqa: E402
import evo_rt as RT    # noqa: E402

FEATURES = os.path.join(KIT, "features")


# ---------- 边界（magpie TestPluginsImportOnlyCore）----------
def _imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            out.add(n.module.split(".")[0])
    return out


def _feature_modules():
    mods = {}
    for d in sorted(glob.glob(os.path.join(FEATURES, "*", "feature.json"))):
        fid = os.path.basename(os.path.dirname(d))
        for py in glob.glob(os.path.join(os.path.dirname(d), "*.py")):
            mods[os.path.splitext(os.path.basename(py))[0]] = fid
    return mods


def _kernel_files():
    return [os.path.join(KIT, "bin", "evo")] + sorted(glob.glob(os.path.join(KIT, "bin", "*.py")))


def test_kernel_imports_no_feature():
    mods = _feature_modules()
    assert mods, "kit/features 下应当有功能包"
    for f in _kernel_files():
        bad = (_imports(f) & set(mods)) - {"feature"}
        assert not bad, f"内核文件 {f} import 了功能包模块 {bad}（内核只经运行时的服务 / 槽位 / 事件用功能）"
        assert "features" not in _imports(f), f


def test_features_do_not_import_each_other():
    mods = _feature_modules()
    for py in glob.glob(os.path.join(FEATURES, "*", "*.py")):
        fid = os.path.basename(os.path.dirname(py))
        for m in _imports(py):
            assert mods.get(m, fid) == fid or m == "feature", f"{py} import 了别的功能包的 {m}（{mods.get(m)}）：只能经服务 / 事件"


def test_feature_module_names_unique():
    seen = {}
    for py in glob.glob(os.path.join(FEATURES, "*", "*.py")):
        name = os.path.basename(py)
        if name == "feature.py":
            continue
        assert name not in seen, f"{name} 在 {seen.get(name)} 和 {py} 都有（模块名要全局唯一）"
        seen[name] = py
        assert not os.path.exists(os.path.join(KIT, "bin", name)), f"{name} 内核里也有一份"


def test_every_manifest_valid():
    for mp in glob.glob(os.path.join(FEATURES, "*", "feature.json")):
        d = os.path.basename(os.path.dirname(mp))
        m = json.load(open(mp, encoding="utf-8"))
        assert RT.validate_manifest(m, d) == [], (d, RT.validate_manifest(m, d))
        assert RT.api_matches(m["api"])
        assert os.path.exists(os.path.join(os.path.dirname(mp), m.get("entry") or "feature.py"))


# ---------- 运行时单元 ----------
def _fake_feature(root, fid, body, **m):
    d = os.path.join(root, fid)
    os.makedirs(d)
    man = {"id": fid, "api": "^1", "name": fid, **m}
    json.dump(man, open(os.path.join(d, "feature.json"), "w"))
    open(os.path.join(d, "feature.py"), "w").write(body)
    return d


def test_runtime_reconcile_services_and_failure_isolated(tmp_path):
    fd = tmp_path / "features"
    _fake_feature(str(fd), "aa", "def apply(ctx):\n    ctx.provide('svc.a', 41)\n", provides=["svc.a"])
    _fake_feature(str(fd), "bb", "def apply(ctx):\n    ctx.provide('svc.b', ctx.service('svc.a') + 1)\n",
                  requires=["svc.a"], provides=["svc.b"])
    _fake_feature(str(fd), "cc", "def apply(ctx):\n    raise RuntimeError('坏了')\n")
    _fake_feature(str(fd), "dd", "def apply(ctx):\n    pass\n", requires=["svc.none"])
    _fake_feature(str(fd), "ee", "def apply(ctx):\n    pass\n", api="^2")
    r = RT.Runtime(str(fd), str(tmp_path)).refresh(force=True)
    st = {f["id"]: f for f in r.dump()}
    assert st["aa"]["state"] == st["bb"]["state"] == "active"
    assert r.service("svc.b") == 42
    assert st["cc"]["state"] == "failed" and "坏了" in st["cc"]["why"]
    assert st["dd"]["state"] == "pending" and "svc.none" in st["dd"]["why"]
    assert st["ee"]["state"] == "failed" and "不兼容" in st["ee"]["why"]
    # 关掉 aa：依赖它的 bb 跟着撤（新的先撤），服务没了
    r.set_enabled("aa", False)
    st = {f["id"]: f for f in r.dump()}
    assert st["aa"]["state"] == "off" and st["bb"]["state"] == "pending" and r.service("svc.b") is None
    r.set_enabled("aa", True)
    assert r.service("svc.b") == 42


def test_runtime_in_use_cannot_turn_off_and_schema(tmp_path):
    fd = tmp_path / "features"
    schema = {"type": "object", "x-order": ["n", "mode"], "properties": {
        "n": {"type": "integer", "title": "次数", "minimum": 0, "maximum": 9, "default": 3},
        "mode": {"type": "string", "title": "模式", "enum": ["a", "b"], "default": "a"}}}
    _fake_feature(str(fd), "used", "def apply(ctx):\n    pass\ndef in_use(k, cfg):\n    return 2\n", many="{n} 个东西")
    _fake_feature(str(fd), "conf", "def apply(ctx):\n    ctx.provide('conf.n', ctx.config['n'])\n", provides=["conf.n"], settings=schema)
    r = RT.Runtime(str(fd), str(tmp_path)).refresh(force=True)
    with pytest.raises(RT.FeatureError, match="2 个东西"):
        r.set_enabled("used", False)
    assert r.service("conf.n") == 3
    r.set_config("conf", {"n": 7})
    assert r.service("conf.n") == 7 and "n: 7" in open(r.path).read()
    with pytest.raises(RT.FeatureError):
        r.set_config("conf", {"n": 99})
    with pytest.raises(RT.FeatureError):
        r.set_config("conf", {"mode": "zz"})
    # 手改进来不合 schema 的值：不用它，默认值顶上
    open(r.path, "w").write("preset: all\nfeatures:\n  - id: conf\n    config:\n      n: 1000\n")
    r.refresh(force=True)
    assert r.service("conf.n") == 3
    # 精简预设：不是 essential 的关；在用的仍开
    r.set_preset("essentials")
    st = {f["id"]: f for f in r.dump()}
    assert st["conf"]["state"] == "off" and st["used"]["state"] == "active" and st["used"]["source"] == "in_use"


def test_broken_features_yml_is_kept_and_refused(tmp_path):
    fd = tmp_path / "features"
    _fake_feature(str(fd), "aa", "def apply(ctx):\n    pass\n")
    open(tmp_path / "features.yml", "w").write("preset: nonsense\n")
    r = RT.Runtime(str(fd), str(tmp_path)).refresh(force=True)
    assert r.file_error and r.dump()[0]["state"] == "active"         # 读坏了：照全开跑，文件留着
    with pytest.raises(RT.FeatureError, match="坏了"):
        r.set_enabled("aa", False)
    assert open(tmp_path / "features.yml").read() == "preset: nonsense\n"


def test_yml_roundtrip():
    doc = {"preset": "essentials", "features": [{"id": "a", "enabled": False}, {"id": "b", "config": {"x": 3, "s": "a: b", "f": True}}]}
    back = RT.parse_yml(RT.dump_yml(doc))
    assert back["preset"] == "essentials" and back["features"] == doc["features"]


# ---------- 总线 ----------
def test_bus_isolates_errors_and_timeouts(tmp_path):
    log = tmp_path / "events.jsonl"
    b = BUS.Bus(str(log), "AB")
    got = []
    b.subscribe("item.*", lambda ev: 1 / 0, owner="bad")
    b.subscribe("item.created", lambda ev: time.sleep(5), owner="slow", timeout=0.2)
    b.subscribe("item.created", lambda ev: got.append(ev["data"]["x"]), owner="good", priority=90)
    b.publish("item.created", {"x": 1}, item="AB-FIX-001")
    assert got == [1]
    owners = {e["owner"] for e in b.errors}
    assert owners == {"bad", "slow"}
    lines = [json.loads(x) for x in open(log, encoding="utf-8")]
    assert lines[0]["event"] == "item.created" and lines[0]["schema_version"] == 1 and lines[0]["item"] == "AB-FIX-001"
    assert {x["data"].get("feature") for x in lines if x["event"] == "feature.error"} == {"bad", "slow"}


def test_watch_tails_events(tmp_path):
    log = tmp_path / "events.jsonl"
    b = BUS.Bus(str(log), "AB")
    b.publish("tick", {})

    class Out:
        def __init__(self):
            self.lines = []

        def write(self, s):
            self.lines += [x for x in s.splitlines() if x]

        def flush(self):
            pass
    out = Out()
    done = time.time() + 1.5
    t = threading.Thread(target=BUS.watch, kwargs=dict(log_path=str(log), out=out, replay=5, ping=0, poll=0.05,
                                                        stop=lambda: time.time() > done))
    t.start()
    time.sleep(0.3)
    b.publish("gate.pending", {"gate": "g1"})
    t.join()
    evs = [json.loads(x)["event"] for x in out.lines]
    assert evs[0] == "watch.ping" and "tick" in evs and "gate.pending" in evs
    assert all(json.loads(x)["schema_version"] == 1 for x in out.lines)


# ---------- 整机：evo feature / watch / 槽位 ----------
def test_feature_cli_list_off_on(loop):
    loop.project("AB")
    d = json.loads(loop.ok("feature", "dump", "--json").stdout)
    assert d["schema_version"] == 1 and d["api"] == "1.0"
    ids = {f["id"]: f for f in d["features"]}
    assert ids["ui-preset"]["state"] == "active"
    loop.ok("feature", "off", "ui-preset")
    r = loop.evo("-p", "AB", "ui", "show")
    assert r.returncode != 0 and "evo feature on ui-preset" in (r.stderr + r.stdout)
    loop.ok("feature", "on", "ui-preset")
    assert json.loads(loop.ok("feature", "list", "--json").stdout)["features"]


def test_ui_preset_in_use_refuses_off(loop):
    loop.project("AB")
    loop.patch_cfg("AB", ui_preset="web-react")
    r = loop.evo("feature", "off", "ui-preset")
    assert r.returncode == 2 and "正在用" in r.stderr


def test_events_written_for_item_lifecycle(loop):
    loop.project("AB")
    loop.add("AB")
    evs = [json.loads(x) for x in open(os.path.join(loop.root, "events.jsonl"), encoding="utf-8")]
    created = [e for e in evs if e["event"] == "item.created"]
    assert created and created[0]["project"] == "AB" and created[0]["item"].startswith("AB-FIX-")
    r = loop.evo("watch", "--json", "--replay", "50", "--seconds", "1", "--ping", "0")
    lines = [json.loads(x) for x in r.stdout.splitlines()]
    assert lines[0]["event"] == "watch.ping" and any(x["event"] == "item.created" for x in lines)


def test_no_undefined_names_in_kernel_and_features():
    """搬家最容易漏的是名字（内核的全局名要写成 K.xxx）：有 ruff 就查一遍 F821。"""
    ruff = shutil.which("ruff")
    if not ruff:
        pytest.skip("没装 ruff")
    files = glob.glob(os.path.join(FEATURES, "*", "*.py")) + _kernel_files()[1:]
    r = subprocess.run([ruff, "check", "--no-cache", "--select", "F821", *files], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:]
    r = subprocess.run([ruff, "check", "--no-cache", "--select", "F821", "--stdin-filename", "evo.py"],     # 没扩展名的 evo 本体
                       stdin=open(_kernel_files()[0], encoding="utf-8"), capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:]
