"""第十三轮：UI 栈预设（kit/presets/ui）。项目配置 ui_preset / ui_overrides、evo ui show|set|check、
new/import --ui-preset、碰界面的件任务书里带「UI 规范」、交卷时依赖检查（禁用库打回、lockfile/手写组件只提示）、
现有栈优先且只报一次、ST 档案用 swiftui、TB 不动。"""
import json, os, sys

from conftest import KIT, state_is

sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_ui as UI  # noqa: E402

K = "AB-FIX-001"
PRINCIPLES = ["优先复用成熟库", "组件源代码可控", "统一设计语言", "严格限制重复依赖"]


def events(loop, key=K):
    return json.loads(loop.ok("-p", "AB", "log", key, "--json").stdout)["events"]


def commit(loop, repo, rel, text, msg="init deps"):
    p = os.path.join(repo, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(text)
    loop.git(repo, "add", rel); loop.git(repo, "commit", "-qm", msg)
    loop.git(repo, "push", "-q", "origin", "main", check=False)


def pkg(**deps):
    return json.dumps({"name": "web", "dependencies": {k.replace("__", "/").replace("_", "-"): "^1" for k in deps}})


# ---------- 1 预设文件 ----------
def test_preset_files_have_categories_banned_principles_and_rules():
    web, sw = UI.load_preset("web-react"), UI.load_preset("swiftui")
    assert UI.load_preset("none") is None
    for pre in (web, sw):
        assert pre["principles"] == PRINCIPLES and pre["rules"]
        for c in pre["categories"].values():
            assert c["label"] and c["choice"] and c["source"] in ("owner", "suggested") and isinstance(c["banned"], list)
    c = web["categories"]
    assert c["ui"]["source"] == "owner" and "Nova" in c["ui"]["choice"] and "@mui/*" in c["ui"]["banned"] and "antd" in c["ui"]["banned"]
    assert c["icons"]["packages"] == ["lucide-react"] and {"@heroicons/react", "react-icons", "@fortawesome/*"} <= set(c["icons"]["banned"])
    assert "motion" in c["animation"]["packages"] and {"react-spring", "gsap"} <= set(c["animation"]["banned"])
    assert c["state"]["packages"] == ["zustand"] and {"redux", "jotai", "mobx"} <= set(c["state"]["banned"])
    assert c["layout"]["packages"] == ["react-resizable-panels"] and c["dnd"]["packages"] == ["@dnd-kit/*"]
    for n in ("forms", "data", "tables", "toasts", "charts", "dates"):
        assert c[n]["source"] == "suggested"
    assert "SF Symbols" in sw["categories"]["icons"]["choice"] and "lottie-ios" in sw["categories"]["animation"]["banned"]
    readme = open(os.path.join(KIT, "presets", "ui", "README.md"), encoding="utf-8").read()
    assert all(p in readme for p in PRINCIPLES) and "TB" in readme


# ---------- 2 配置与命令 ----------
def test_default_none_adds_nothing_and_ui_set_show(loop):
    loop.project("AB")
    assert "none" in loop.ok("-p", "AB", "ui").stdout and loop.status_json("AB")["ui_preset"] == "none"
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.tick("AB")
    assert all("（预设" not in w["spec"] for w in loop.workers())   # 岗位说明里本来就有「UI 规范」小节，认块的开头
    loop.ok("-p", "AB", "ui", "set", "web-react")
    assert json.load(open(loop.cfg_path("AB")))["ui_preset"] == "web-react"
    out = loop.ok("-p", "AB", "ui", "show").stdout
    assert "lucide-react" in out and "不另加" in out and "严格限制重复依赖" in out
    loop.ok("-p", "AB", "ui", "set", "icons=@tabler/icons-react")
    assert json.load(open(loop.cfg_path("AB")))["ui_overrides"] == {"icons": ["@tabler/icons-react"]}
    eff = json.loads(loop.ok("-p", "AB", "ui", "--json").stdout)["effective"]
    assert "lucide-react" in eff["categories"]["icons"]["banned"] and "@tabler/icons-react" not in eff["categories"]["icons"]["banned"]
    loop.ok("-p", "AB", "ui", "set", "icons=")
    assert "ui_overrides" not in json.load(open(loop.cfg_path("AB")))
    assert loop.evo("-p", "AB", "ui", "set", "bootstrap5").returncode != 0
    assert loop.evo("-p", "AB", "ui", "set", "icons=rm -rf").returncode != 0
    loop.env["EVO_AGENT"] = "muse"
    r = loop.evo("-p", "AB", "ui", "set", "swiftui")
    assert r.returncode != 0 and "外部 Agent" in (r.stdout + r.stderr)
    assert loop.evo("-p", "AB", "ui", "show").returncode == 0                  # 看可以
    del loop.env["EVO_AGENT"]
    loop.ok("-p", "AB", "ui", "set", "none")
    assert "ui_preset" not in json.load(open(loop.cfg_path("AB")))


def test_new_and_import_accept_ui_preset(loop):
    repo = os.path.join(loop.tmp, "repos", "CD")
    os.makedirs(repo); loop.git(repo, "init", "-q", "-b", "main")
    open(os.path.join(repo, "package.json"), "w").write(pkg(react_icons=1))
    loop.git(repo, "add", "package.json"); loop.git(repo, "commit", "-qm", "i")
    r = loop.ok("import", "CD", "--name", "项目CD", "--path", repo, "--test", "true", "--ui-preset", "web-react")
    assert json.load(open(loop.cfg_path("CD")))["ui_preset"] == "web-react"
    assert "react-icons" in r.stdout and "现有的赢" in r.stdout                  # 导入时就把冲突说一次
    loop.ok("new", "EF", "--name", "项目EF", "--path", os.path.join(loop.tmp, "repos", "EF"), "--ui-preset", "swiftui")
    assert json.load(open(loop.cfg_path("EF")))["ui_preset"] == "swiftui"
    loop.ok("new", "GH", "--name", "项目GH", "--path", os.path.join(loop.tmp, "repos", "GH"))
    assert "ui_preset" not in json.load(open(loop.cfg_path("GH")))
    assert loop.evo("new", "IJ", "--name", "x", "--path", os.path.join(loop.tmp, "repos", "IJ"), "--ui-preset", "vue").returncode != 0
    assert not os.path.exists(os.path.join(loop.tmp, "repos", "IJ"))           # 先校验再建仓库


# ---------- 3 任务书注入 ----------
def test_ui_block_only_for_items_touching_ui_and_after_goal(loop):
    loop.project("AB", goal="让布艺店主十分钟上架一款新品", ui_preset="web-react")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])                        # look
    loop.ok("-p", "AB", "add", "--kind", "ops", "--title", "调整夜间对账任务", "--scope", "ops/")   # 不碰界面
    loop.ok("-p", "AB", "add", "--kind", "feat", "--title", "新增上架表单组件", "--scope", "app/src/components/")  # ui 路径，没打 look
    st = loop.state("AB")["items"]
    b = st[K]["build_spec"]
    assert b.startswith("项目目标：让布艺店主十分钟上架一款新品\n\nUI 规范（预设 web-react")
    assert b.index("UI 规范（预设") < b.index("施工岗") and "lucide-react" in b.split("施工岗")[0] and "shadcn" in b
    v = st[K]["verify_spec"]
    assert "UI 规范检查（预设 web-react" in v and "evo -p AB ui check" in v and "建议另开 issue" in v and v.index("UI 规范检查（预设") < v.index("验收岗")
    assert "（预设" not in st["AB-OPS-001"]["build_spec"] and "（预设" not in st["AB-OPS-001"]["verify_spec"]
    assert "UI 规范（预设 web-react" in st["AB-FEAT-001"]["build_spec"]
    loop.plan(verify=["fail"])                                                 # 返工的任务书也带
    loop.run_until("AB", lambda s: s["items"][K]["round"] >= 1)
    assert "UI 规范（预设 web-react" in loop.item("AB", K)["build_spec"]
    builds = [w for w in loop.workers() if w["role"] == "build" and "改版注册页按钮" in w["spec"]]
    assert len(builds) >= 2 and all("UI 规范（预设" in w["spec"] for w in builds)


def test_swiftui_block_for_views_scope(loop):
    loop.project("AB", ui_preset="swiftui")
    loop.ok("-p", "AB", "add", "--kind", "ux", "--title", "调整行情页布局", "--scope", "App/Sources/App/Views/")
    b = loop.item("AB")["build_spec"]
    assert b.startswith("UI 规范（预设 swiftui") and "SF Symbols" in b and "lottie-ios" in b and "老板批准" in b


# ---------- 4 交卷时的依赖检查 ----------
def test_banned_dependency_rejected_before_verify(loop):
    loop.project("AB", ui_preset="web-react")
    loop.plan(build=["dep:react-icons"])
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", lambda s: s["items"][K]["round"] >= 1)
    rw = [e for e in events(loop) if e["event"] == "rework"]
    assert rw and "react-icons" in rw[0]["why"] and "图标" in rw[0]["why"] and "ui_overrides" in rw[0]["why"]
    assert not [w for w in loop.workers() if w["role"] == "verify"]            # 没送验收


def test_preset_lib_passes_and_unexplained_new_dep_is_advisory(loop):
    loop.project("AB", ui_preset="web-react")
    loop.plan(build=["dep:lucide-react"])
    loop.add("AB", "改版注册页按钮", "web/")
    loop.run_until("AB", state_is("merged"))
    assert loop.item("AB")["round"] == 0
    loop.plan(build=["dep:left-pad"])
    loop.add("AB", "修复注册页提示文字", "web/")
    loop.run_until("AB", state_is("merged", "AB-FIX-002"))
    adv = [e for e in events(loop, "AB-FIX-002") if e["event"] == "ui_advisory"]
    assert adv and "left-pad" in adv[0]["notes"][0] and loop.item("AB", "AB-FIX-002")["round"] == 0


def test_override_allows_lib_and_bans_preset_choice(loop):
    loop.project("AB", ui_preset="web-react", ui_overrides={"icons": "react-icons"})
    loop.plan(build=["dep:react-icons"])
    loop.add("AB", "改版注册页按钮", "web/")
    loop.run_until("AB", state_is("merged"))
    loop.plan(build=["dep:lucide-react"])
    loop.add("AB", "修复注册页提示文字", "web/")
    loop.run_until("AB", lambda s: s["items"]["AB-FIX-002"]["round"] >= 1)
    assert "lucide-react" in [e for e in events(loop, "AB-FIX-002") if e["event"] == "rework"][0]["why"]


def test_handrolled_component_is_advisory_only(loop):
    loop.project("AB", ui_preset="web-react")
    loop.plan(build=["file:web/src/widgets/Modal.tsx"])
    loop.add("AB", "改版注册页按钮", "web/")
    loop.run_until("AB", state_is("merged"))
    adv = [e for e in events(loop) if e["event"] == "ui_advisory"]
    assert adv and "Modal.tsx" in adv[0]["notes"][0] and "dialog" in adv[0]["notes"][0]


def test_no_preset_no_dependency_check(loop):
    loop.project("AB")
    loop.plan(build=["dep:react-icons"])
    loop.add("AB")
    loop.run_until("AB", state_is("merged"))
    assert loop.item("AB")["round"] == 0 and not [e for e in events(loop) if e["event"] == "ui_advisory"]


# ---------- 5 现有栈优先，只报一次 ----------
def test_existing_conflicting_lib_wins_and_reported_once(loop):
    repo = loop.project("AB", ui_preset="web-react")
    commit(loop, repo, "web/package.json", pkg(react_icons=1, zustand=1))
    out = loop.ok("-p", "AB", "ui").stdout
    assert "沿用仓库现有的 react-icons" in out
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    assert "沿用仓库现有的 react-icons" in loop.item("AB")["build_spec"]
    for _ in range(3):
        loop.tick("AB")
    logs = [l for l in loop.state("AB")["log"] if "现有的赢" in l]
    assert len(logs) == 1 and "react-icons" in logs[0]
    assert len([e for e in loop.outbox() if e["kind"] == "ui_conflict"]) == 1
    eff = UI.effective({"ui_preset": "web-react"}, present={"react-icons", "zustand"})
    assert "lucide-react" in eff["categories"]["icons"]["banned"]               # 现有的赢：再加 lucide 算重复
    assert "react-icons" not in eff["categories"]["icons"]["banned"]
    assert eff["categories"]["state"]["existing"] == []


def test_existing_lib_alongside_preset_keeps_preset_choice():
    eff = UI.effective({"ui_preset": "web-react"}, present={"lucide-react", "react-icons"})
    c = eff["categories"]["icons"]
    assert not c["kept"] and c["choice"].startswith("Lucide") and "lucide-react" not in c["banned"]
    assert eff["conflicts"] == [{"category": "icons", "label": "图标", "existing": ["react-icons"], "kept": False}]


def test_swift_package_detection_and_ui_check_cli(loop):
    repo = loop.project("AB", ui_preset="swiftui")
    commit(loop, repo, "Package.swift", 'let p = Package(dependencies: [\n  .package(url: "https://github.com/airbnb/lottie-spm.git", from: "4.0.0")\n])\n')
    assert "沿用仓库现有的 lottie-spm" in loop.ok("-p", "AB", "ui").stdout
    base = loop.git(repo, "rev-parse", "HEAD")
    commit(loop, repo, "Package.swift", 'let p = Package(dependencies: [\n  .package(url: "https://github.com/airbnb/lottie-spm.git", from: "4.0.0"),\n'
           '  .package(url: "https://github.com/SnapKit/SnapKit.git", from: "5.0.0"),\n  .package(url: "https://github.com/danielgindi/Charts", from: "5.0.0")\n])\n', "add deps")
    r = loop.evo("-p", "AB", "ui", "check", "--path", repo, "--base", base, "--json")
    assert r.returncode == 1, r.stdout + r.stderr
    j = json.loads(r.stdout)
    assert {v["package"] for v in j["violations"]} == {"SnapKit", "Charts"}
    r = loop.evo("-p", "AB", "ui", "check", "--path", repo, "--base", base)
    assert r.returncode == 1 and "SnapKit" in r.stdout and "不合规" in r.stdout


def test_ui_check_lockfile_only_is_advisory(loop):
    repo = loop.project("AB", ui_preset="web-react")
    commit(loop, repo, "web/package.json", pkg(recharts=1))
    base = loop.git(repo, "rev-parse", "HEAD")
    commit(loop, repo, "web/package-lock.json", json.dumps({"packages": {"": {}, "node_modules/recharts": {}, "node_modules/moment": {}}}), "lock")
    r = loop.evo("-p", "AB", "ui", "check", "--path", repo, "--base", base, "--json")
    assert r.returncode == 0
    j = json.loads(r.stdout)
    assert j["violations"] == [] and [x["package"] for x in j["lock_only"]] == ["moment"]


# ---------- 6 档案 ----------
def test_st_profile_swiftui_and_tb_untouched():
    st = json.load(open(os.path.join(KIT, "profiles", "st", "project.json"), encoding="utf-8"))
    tb = json.load(open(os.path.join(KIT, "profiles", "tubu", "project.json"), encoding="utf-8"))
    assert st["ui_preset"] == "swiftui" and "ui_preset" not in tb
    eff = UI.effective(st, present=set())
    assert UI.touches_ui({"scope": ["REASTOCK/Sources/REASTOCK/Views/"]}, eff)
    assert not UI.touches_ui({"scope": ["REASTOCK/Sources/REASTOCK/Engine/"]}, eff)


def test_ui_show_preview_does_not_change_config(loop):
    repo = loop.project("AB")
    commit(loop, repo, "web/package.json", pkg(antd=1))
    out = loop.ok("-p", "AB", "ui", "show", "web-react").stdout
    assert "沿用仓库现有的 antd" in out and "ui_preset" not in json.load(open(loop.cfg_path("AB")))
