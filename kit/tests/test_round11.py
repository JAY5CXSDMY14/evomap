"""第十一轮：看效果指纹（返工改了看过的内容才重看）、死掉的工人自动重启一次、ponytail 进岗位、
施工/验收模型核对（magpie /v1/models）与面板单项目覆盖。"""
import json, os, subprocess, sys, urllib.parse

from conftest import EVO, KIT, state_is
from test_agents_panel import free_port, req

WORKER = os.path.join(KIT, "tests", "fakes", "worker.py")
K = "AB-FIX-001"
SHA = "09c434ab73ca43761c5d8b0c5d341926c2fba710"


def at(day, hm):
    """EVO_NOW 用的 ISO 时间（上海）。"""
    return f"{day}T{hm}:00" + "+08:00"


def builds(loop):
    return [w for w in loop.workers() if w["role"] == "build"]


def look_gates(loop):
    return [g for g in loop.orca_state()["gates"].values() if g["question"].startswith("看效果")]


# ---------- 1 看效果指纹 ----------
def approved_look_item(loop, plan_build=None):
    """一件要看效果的件：合并前测试第一次红（C6 自动返工），老板在返工前已经点了「通过」。"""
    cnt = os.path.join(loop.tmp, "runs")
    loop.project("AB", test_cmd=f"n=$(cat {cnt} 2>/dev/null || echo 0); echo $((n+1)) > {cnt}; test $n -ge 1")
    if plan_build:
        loop.plan(build=plan_build)
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))
    g = loop.status_json("AB")["gates"][0]
    assert g["kind"] == "look"
    loop.ok("-p", "AB", "approve", g["id"], "通过")
    it = loop.item("AB")
    assert it["look_patch"] and it["look_sha"]
    return it


def test_relook_when_rework_changed_looked_content(loop):
    approved_look_item(loop)
    st = loop.run_until("AB", lambda s: s["items"][K].get("relooks") or s["items"][K]["state"] in ("pushing", "merged"), n=10)
    it = st["items"][K]
    assert it["round"] == 1 and it["relooks"] == 1 and it["state"] == "verified"     # 返工改了内容：不合并，重开闸门
    assert "look_patch" not in it
    g = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "look"]
    assert len(g) == 1 and "改动后重看" in g[0]["question"] and g[0]["id"] == it["gates"]["look"]
    ev = [e for e in loop.outbox() if e["kind"] == "gate_created" and "解冲突/返工时改了你看过的内容" in json.dumps(e, ensure_ascii=False)]
    assert len(ev) == 1
    loop.tick("AB")
    assert loop.item("AB")["state"] == "verified"                                    # 没点就一直等
    loop.env["EVO_NOW"] = at("2026-10-20", "12:06")
    loop.tick("AB")
    assert any("改动后重看" in m["text"] and "reply_markup" in m for m in loop.telegram_sent())   # 和普通看效果闸门一样推送
    loop.ok("-p", "AB", "approve", g[0]["id"], "通过")
    loop.run_until("AB", state_is("merged"))
    assert len(look_gates(loop)) == 2


def test_no_relook_when_rework_kept_patch(loop):
    approved_look_item(loop, plan_build=["ok", "same"])                             # 返工那轮什么都没改
    st = loop.run_until("AB", state_is("merged"), n=10)
    it = st["items"][K]
    assert it["round"] == 1 and not it.get("relooks")
    assert len(look_gates(loop)) == 1
    assert not any("解冲突/返工时改了你看过的内容" in json.dumps(e, ensure_ascii=False) for e in loop.outbox())


def test_relook_can_be_turned_off(loop):
    loop.write_global({"relook_on_change": False})
    approved_look_item(loop)
    st = loop.run_until("AB", state_is("merged"), n=10)
    assert st["items"][K]["round"] == 1 and not st["items"][K].get("relooks") and len(look_gates(loop)) == 1


def test_look_reject_clears_fingerprint(loop):
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))
    g = loop.status_json("AB")["gates"][0]["id"]
    loop.ok("-p", "AB", "approve", g, "打回", "按钮太小")
    it = loop.item("AB")
    assert "look_patch" not in it and it["round"] == 1


# ---------- 2 C7 死掉的工人自动重启一次 ----------
def test_dead_builder_restarted_once_same_worktree_and_model(loop):
    loop.project("AB")
    loop.plan(build=["die"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"), n=8)
    it = st["items"][K]
    b = builds(loop)
    assert len(b) == 2 and b[0]["cwd"] == b[1]["cwd"] and "自动重启一次" in b[1]["spec"]
    assert it["restarts"] == 1 and it["round"] == 0 and it["dispatch"]["build"]["restarts"] == 1
    assert it["dispatch"]["build"]["model"] == "model-a"
    assert any("工人进程不在了，已在原工作区自动重启一次" in l and "model-a" in l for l in st["log"])
    assert not any(e["kind"] == "stalled" for e in loop.outbox())
    assert any(e["kind"] == "worker_restarted" for e in loop.outbox())


def test_dead_verifier_restarted_once(loop):
    loop.project("AB")
    loop.plan(verify=["die"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"), n=8)
    v = [w for w in loop.workers() if w["role"] == "verify"]
    assert len(v) == 2 and st["items"][K]["restarts"] == 1 and len(builds(loop)) == 1


def test_second_death_same_dispatch_falls_back_to_stall_alert(loop):
    loop.project("AB")
    loop.plan(build=["die", "die"])
    loop.add("AB")
    for _ in range(3):
        loop.tick("AB")
    it = loop.item("AB")
    assert it["stalled"] and it["state"] == "building" and it["restarts"] == 1 and len(builds(loop)) == 2
    st = [e for e in loop.outbox() if e["kind"] == "stalled"]
    assert len(st) == 1 and "工人进程不在了" in st[0]["body"]


def test_worker_that_already_reported_is_not_restarted(loop):
    loop.project("AB")
    loop.add("AB")
    loop.env["FAKE_WORKER_STATUS"] = "dead"            # 交完 worker_done 进程就退了：回报下一轮处理，不重复派工
    loop.tick("AB")
    loop.env.pop("FAKE_WORKER_STATUS")
    assert len(builds(loop)) == 1 and not loop.item("AB").get("restarts")
    loop.run_until("AB", state_is("merged"))
    assert len(builds(loop)) == 1


# ---------- 3 ponytail ----------
def test_vendor_ponytail_pinned_with_license():
    d = os.path.join(KIT, "vendor", "ponytail")
    readme = open(os.path.join(d, "README.md"), encoding="utf-8").read()
    assert SHA in readme and "MIT" in readme and "DietrichGebert/ponytail" in readme
    assert open(os.path.join(d, "LICENSE"), encoding="utf-8").read().startswith("MIT License")
    assert "name: ponytail\n" in open(os.path.join(d, "ponytail", "SKILL.md"), encoding="utf-8").read()
    assert "name: ponytail-review" in open(os.path.join(d, "ponytail-review", "SKILL.md"), encoding="utf-8").read()


def test_role_prompts_carry_ponytail_and_point_to_vendor(loop):
    loop.project("AB")
    loop.add("AB")
    tasks = loop.orca_state()["tasks"]
    it = loop.item("AB")
    b, v = tasks[it["build"]]["spec"], tasks[it["verify"]]["spec"]
    assert os.path.join(KIT, "vendor/ponytail/ponytail/SKILL.md") in b and "{KIT}" not in b
    assert "full 档" in b and "ultra" in b and "shortcut:" in b and "unfinished" in b and "risks" in b
    assert "验收标准压过「最少代码」" in b
    assert os.path.join(KIT, "vendor/ponytail/ponytail-review/SKILL.md") in v and "{KIT}" not in v
    assert "必须修" in v and "应该修" in v and "触发情形" in v


def test_weekly_audit_todo_on_sunday_only_once(loop):
    loop.write_global({"roles": {"decide": {"cmd": f"{sys.executable} {WORKER} decide", "models": ["model-x"],
                                            "prompt": "roles/decider.md", "boot_seconds": 0}}})
    loop.project("AB")
    loop.env["EVO_NOW"] = at("2026-10-19", "23:40")
    loop.ok("-p", "AB", "once")
    assert not loop.state("AB").get("decide_inbox")                              # 周一不放
    loop.env["EVO_NOW"] = at("2026-10-25", "23:40")
    loop.ok("-p", "AB", "once")
    todo = [e for e in loop.state("AB")["decide_inbox"] if e.get("todo")]
    assert len(todo) == 1 and "ponytail-audit" in todo[0]["note"]
    loop.env["EVO_NOW"] = at("2026-10-25", "23:50")
    loop.ok("-p", "AB", "once")                                                 # 同一晚不重复；这一轮叫醒决策岗
    dec = [w for w in loop.workers() if w["role"] == "decide"]
    assert len(dec) == 1 and "例行待办" in dec[0]["spec"] and "ponytail-audit" in dec[0]["spec"]
    assert "## 外部来报" not in dec[0]["spec"]
    assert loop.state("AB")["decide_inbox"] == []


def test_audit_weekday_configurable(loop):
    loop.write_global({"audit_weekday": 0})
    loop.project("AB")
    loop.env["EVO_NOW"] = at("2026-10-25", "23:40")
    loop.ok("-p", "AB", "once")
    assert not loop.state("AB").get("decide_inbox")
    loop.env["EVO_NOW"] = at("2026-10-26", "23:40")
    loop.ok("-p", "AB", "once")
    assert [e["title"] for e in loop.state("AB")["decide_inbox"]] == ["每周 ponytail-audit"]


# ---------- 4 模型：magpie 核对 + 单项目覆盖 + 面板 ----------
def set_models(loop, build, verify):
    p = os.path.join(loop.root, "config.json")
    g = json.load(open(p))
    g["roles"]["build"]["models"], g["roles"]["verify"]["models"] = build, verify
    json.dump(g, open(p, "w"), ensure_ascii=False)


MAGPIE = {"object": "list", "data": [{"id": "group/evo-build", "members": ["glm", "ds"]},
                                     {"id": "group/evo-verify", "members": ["ds", "claude"]}, {"id": "glm"}, {"id": "claude"}]}


def test_models_check_warns_missing_and_overlap(loop):
    set_models(loop, ["group/evo-build"], ["group/evo-verify", "model-x"])
    loop.http_responses({"/v1/models": [MAGPIE]})
    r = loop.evo("models")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "model-x 不在 magpie /v1/models 里" in r.stdout and "group/evo-build 不在" not in r.stdout
    assert "重叠（ds）" in r.stdout
    assert any(x["url"] == "http://127.0.0.1:3425/v1/models" for x in loop.http_log())


def test_models_check_ok_and_magpie_down(loop):
    set_models(loop, ["glm"], ["claude"])
    loop.http_responses({"/v1/models": [MAGPIE]})
    r = loop.evo("models")
    assert r.returncode == 0 and "✓ 施工/验收模型都在 magpie 里" in r.stdout
    set_models(loop, ["glm"], ["glm", "claude"])
    r = loop.evo("models")                                                   # magpie 没响应：跳过列表核对，重叠照样查
    assert r.returncode == 1 and "magpie 没响应" in r.stdout and "重叠（glm）" in r.stdout


def test_project_override_set_clear_validated_and_agents_refused(loop):
    loop.project("AB")
    loop.ok("-p", "AB", "models", "set", "build", "model-b")
    c = json.load(open(loop.cfg_path("AB")))
    assert c["overrides"]["roles"]["build"]["models"] == ["model-b"]
    loop.add("AB")
    loop.tick("AB")
    assert loop.item("AB")["dispatch"]["build"]["model"] == "model-b"           # 下一次派工就用覆盖的模型
    for bad in ("a;rm -rf /", "x y", ""):
        r = loop.evo("-p", "AB", "models", "set", "verify", bad)
        assert r.returncode != 0
    assert "verify" not in json.load(open(loop.cfg_path("AB")))["overrides"]["roles"]
    loop.env["EVO_AGENT"] = "muse"
    r = loop.evo("-p", "AB", "models", "clear", "build")
    assert r.returncode != 0 and "外部 Agent" in r.stderr + r.stdout
    loop.env.pop("EVO_AGENT")
    assert json.load(open(loop.cfg_path("AB")))["overrides"]["roles"]["build"]["models"] == ["model-b"]
    loop.ok("-p", "AB", "models", "clear", "build")
    assert "overrides" not in json.load(open(loop.cfg_path("AB")))                # 跟随全局：覆盖整个删掉
    j = json.loads(loop.ok("-p", "AB", "models", "--json").stdout)
    assert j["override"] == {"build": None, "verify": None} and j["follow"]["build"] == ["model-a", "model-b"]


def start_panel(loop, env):
    port = free_port()
    p = subprocess.Popen([sys.executable, EVO, "panel", "--port", str(port)], env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    lines = []
    while True:
        l = p.stdout.readline()
        assert l, "".join(lines)
        lines.append(l)
        if "面板：" in l:
            break
    return p, f"http://127.0.0.1:{port}", open(os.path.join(loop.root, "panel.token")).read().strip()


def post(base, token, body):
    return req(base + "/api/models", json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": f"Bearer {token}"})


def test_panel_model_dropdowns(loop):
    loop.project("AB")
    loop.env["EVO_PANEL_KEYCHAIN"] = "0"
    loop.http_responses({"/v1/models": [MAGPIE] * 3})
    p, base, token = start_panel(loop, loop.env)
    auth = {"Authorization": f"Bearer {token}"}
    try:
        assert req(base + "/api/models/AB")[0] == 401
        assert post(base, "wrong", {"code": "AB", "role": "build", "model": "glm"})[0] == 401
        code, _, body = req(base + "/api/models/AB", headers=auth)
        j = json.loads(body)
        assert code == 200 and j["magpie_ok"] and "group/evo-build" in j["models"]
        assert j["follow"] == {"build": ["model-a", "model-b"], "verify": ["model-a", "model-b"]}
        code, _, body = post(base, token, {"code": "AB", "role": "build", "model": "glm"})
        assert code == 410 and "evo" in json.loads(body)["error"]          # 第二十五轮（#12）：面板只读，改模型用 evo models set
        assert "overrides" not in json.load(open(loop.cfg_path("AB")))
    finally:
        p.terminate(); p.wait(5)


def test_install_runs_models_check(loop):
    home = loop.env["HOME"]
    os.makedirs(os.path.join(home, ".evoloop"), exist_ok=True)
    g = json.load(open(os.path.join(loop.root, "config.json")))
    json.dump(g, open(os.path.join(home, ".evoloop", "config.json"), "w"))
    r = subprocess.run(["bash", os.path.join(KIT, "install.sh")], env=loop.env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "magpie 没响应" in r.stdout and "重叠（model-a, model-b）" in r.stdout      # 只警告，不拦安装


# ---------- 装进 Evo 应用 ----------
def test_install_plist_sets_pythondontwritebytecode(loop):
    fake = os.path.join(loop.tmp, "fakebin"); os.makedirs(fake)
    for name, text in (("uname", "echo Darwin"), ("pmset", "printf ' sleep 0\\n disksleep 0\\n'"), ("launchctl", "exit 0")):
        p = os.path.join(fake, name); open(p, "w").write("#!/bin/bash\n" + text + "\n"); os.chmod(p, 0o755)
    env = {**loop.env, "PATH": fake + os.pathsep + loop.env["PATH"]}
    r = subprocess.run(["bash", os.path.join(KIT, "install.sh"), "--apply"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    plist = open(os.path.join(env["HOME"], "Library", "LaunchAgents", "com.evoloop.autopilot.plist")).read()
    assert "<key>PYTHONDONTWRITEBYTECODE</key><string>1</string>" in plist
    env_block = plist.split("<key>EnvironmentVariables</key>")[1]
    assert "PYTHONDONTWRITEBYTECODE" in env_block


def bundle_macos(loop, kit):
    code = ("import importlib.machinery as m, sys; sys.argv = ['evo']; "
            f"e = m.SourceFileLoader('evo', {os.path.join(kit, 'bin', 'evo')!r}).load_module(); "
            "print(e.IN_APP_BUNDLE, e.GCFG['notify']['macos'])")
    return subprocess.run([sys.executable, "-c", code], env=loop.env, capture_output=True, text=True, check=True).stdout.split()


def test_notify_macos_off_by_default_inside_app_bundle(loop):
    import shutil
    p = os.path.join(loop.root, "config.json")
    g = json.load(open(p)); g["notify"].pop("macos"); json.dump(g, open(p, "w"))
    app_kit = os.path.join(loop.tmp, "Evo.app", "Contents", "Resources", "kit")
    shutil.copytree(KIT, app_kit, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    assert bundle_macos(loop, app_kit) == ["True", "False"]           # 包里：默认关（应用自己发通知）
    assert bundle_macos(loop, KIT) == ["False", "True"]               # 包外：照旧默认开
    g["notify"]["macos"] = True; json.dump(g, open(p, "w"))
    assert bundle_macos(loop, app_kit) == ["True", "True"]            # 显式写了就听配置的


def test_project_models_check_ignores_global_problems(loop):
    # Air 试跑 10-21：全局模板里的模型在 magpie 里不存在，但项目已覆盖 → evo -p 项目 models 不该 exit 1
    set_models(loop, ["group/nope"], ["claude"])
    loop.project("AW")
    loop.http_responses({"/v1/models": [MAGPIE]})
    loop.ok("-p", "AW", "models", "set", "build", "glm")
    loop.http_responses({"/v1/models": [MAGPIE, MAGPIE]})
    r = loop.evo("-p", "AW", "models")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "（全局，不影响 AW）" in r.stdout and "✓ AW 实际用的" in r.stdout
