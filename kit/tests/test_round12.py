"""第十二轮（借 Paperclip 面板 6 处）：无活路检查、看效果闸门内预览产出物、首页岗位状态与卡太久、
每件时间线 + evo log、新反馈作废旧闸门、项目目标进任务书。"""
import json, os, subprocess, sys, urllib.parse

from conftest import EVO, KIT, state_is
from test_agents_panel import NoRedirect, req
import urllib.request
from test_round11 import start_panel

WORKER = os.path.join(KIT, "tests", "fakes", "worker.py")
K = "AB-FIX-001"


def raw(url, headers):
    """取二进制内容（图片）。"""
    op = urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({}))
    r = op.open(urllib.request.Request(url, headers=headers), timeout=10)
    return r.status, r.headers, r.read()


def at(day, hm):
    return f"{day}T{hm}:00" + "+08:00"


def with_decider(loop, **lim):
    loop.write_global({"roles": {"decide": {"cmd": f"{sys.executable} {WORKER} decide", "models": ["model-x"],
                                            "prompt": "roles/decider.md", "boot_seconds": 0}},
                       "limits": lim})


def builds(loop):
    return [w for w in loop.workers() if w["role"] == "build"]


def events(loop, key=K):
    return json.loads(loop.ok("-p", "AB", "log", key, "--json").stdout)["events"]


def nolive_inbox(loop):
    return [e for e in loop.state("AB").get("decide_inbox") or [] if e.get("nolive")]


def look_item_verified(loop, extra=(), **cfg):
    loop.project("AB", **cfg)
    loop.add("AB", "改版注册页按钮", "web/", ["--look", *extra])
    loop.run_until("AB", state_is("verified"))
    g = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "look"]
    assert len(g) == 1
    return g[0]["id"]


# ---------- 1 无活路检查 ----------
def test_no_live_path_flagged_once_after_threshold(loop):
    loop.write_global({"limits": {"rework_rounds": 0}})             # 没配决策岗：交决策岗 = 没人会推它
    loop.project("AB")
    loop.plan(verify=["fail"])
    loop.add("AB")
    loop.run_until("AB", state_is("escalated"))
    loop.tick("AB")
    j = loop.status_json("AB")
    assert j["no_live_path"] == [] and not nolive_inbox(loop)       # 还没到 30 分钟：不标红
    assert next(i for i in j["items"] if i["key"] == K)["no_live_path"] is True   # 但已在计时
    loop.env["EVO_NOW"] = at("2026-10-20", "12:31")
    loop.tick("AB")
    j = loop.status_json("AB")
    assert [n["key"] for n in j["no_live_path"]] == [K] and j["no_live_path"][0]["reason"] == "no_decider"
    assert j["schema_version"] == 1                                 # 只加字段，不升版本
    loop.tick("AB"); loop.tick("AB")
    inbox = nolive_inbox(loop)
    assert len(inbox) == 1 and inbox[0]["item"] == K                # 同件同原因只交一次
    assert [e for e in events(loop) if e["event"] == "no_live_path"]
    assert any(e["kind"] == "no_live_path" for e in loop.outbox())


def test_items_with_a_live_path_are_not_flagged(loop):
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])                     # 会停在「等你看效果」
    loop.add("AB", "修复注册页提示文字", "web/login")                        # 排在上一件后面（依赖）
    loop.ok("-p", "AB", "add", "--kind", "ops", "--title", "调整夜间对账任务", "--scope", "ops/", "--window", "mon-fri 03:00-04:00")
    loop.run_until("AB", state_is("verified", K))
    loop.env["EVO_NOW"] = at("2026-10-20", "13:30")
    loop.tick("AB"); loop.tick("AB")
    j = loop.status_json("AB")
    assert j["no_live_path"] == [] and not nolive_inbox(loop), j["no_live_path"]
    assert not any(i["no_live_path"] for i in j["items"])


def test_no_live_after_idle_decider_goes_back_to_decider_who_can_drop(loop):
    with_decider(loop, rework_rounds=0)
    loop.project("AB")
    loop.plan(verify=["fail"], decide=["pass", {"decisions": [{"item": K, "action": "drop", "note": "需求已取消"}]}])
    loop.add("AB")
    loop.run_until("AB", state_is("escalated"))
    loop.tick("AB")                                                  # 决策岗交了，但没给决定 → 没人会再推它
    assert loop.item("AB")["no_live"]["reason"] == "decider_idle"
    loop.env["EVO_NOW"] = at("2026-10-20", "12:31")
    loop.tick("AB")                                                  # 标红 + 交决策岗 + 同一轮叫醒决策岗
    dec = [w for w in loop.workers() if w["role"] == "decide"]
    assert len(dec) == 2 and "没有活路的件" in dec[1]["spec"] and K in dec[1]["spec"]
    st = loop.run_until("AB", state_is("dropped"), n=3)
    assert "no_live" not in st["items"][K] or loop.status_json("AB")["no_live_path"] == []
    ev = [e["event"] for e in events(loop)]
    assert "decision" in ev and "drop" in ev


# ---------- 2 看效果闸门内预览产出物 ----------
def test_panel_artifacts_preview_item_timeline_and_goal(loop):
    gate = look_item_verified(loop)
    wt = loop.item("AB")["worktree"]
    art = os.path.join(wt, "artifacts"); os.makedirs(os.path.join(art, "shots"))
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    open(os.path.join(art, "shots", "登录 页.png"), "wb").write(png)
    open(os.path.join(art, "report.html"), "w").write("<h1>报告</h1><script>fetch('/api/approve')</script>")
    open(os.path.join(art, "data.csv"), "w").write("a,b\n1,2\n")
    open(os.path.join(art, "big.webp"), "wb").write(b"0" * (5 * 1024 * 1024 + 1))
    os.symlink(os.path.join(loop.repo("AB"), "README.md"), os.path.join(art, "leak.txt"))
    loop.env["EVO_PANEL_KEYCHAIN"] = "0"
    p, base, token = start_panel(loop, loop.env)
    auth = {"Authorization": f"Bearer {token}"}
    A = f"{base}/api/artifact/AB/{K}/"
    try:
        assert req(f"{base}/api/artifacts/AB/{K}")[0] == 401
        assert req(A + "data.csv")[0] == 401
        code, _, body = req(f"{base}/api/artifacts/AB/{K}", headers=auth)
        j = json.loads(body)
        files = {f["path"]: f for f in j["files"]}
        assert code == 200 and set(files) == {"shots/登录 页.png", "report.html", "data.csv", "big.webp"}   # 软链跑出去的不列
        assert files["shots/登录 页.png"]["kind"] == "image" and files["report.html"]["kind"] == "html"
        assert files["data.csv"]["kind"] == "file" and files["big.webp"]["too_big"]
        assert j["manual_checks"] == ["在 1280px 宽度下看注册页"]               # 施工交卷里的人工检查项一起给
        code, hd, body = raw(A + "shots/" + urllib.parse.quote("登录 页.png"), auth)
        assert code == 200 and hd["Content-Type"] == "image/png" and body == png
        code, hd, body = req(A + "report.html", headers=auth)
        assert code == 200 and hd["Content-Type"].startswith("text/plain") and hd["X-Content-Type-Options"] == "nosniff"
        assert "sandbox" in hd["Content-Security-Policy"] and "<h1>报告</h1>" in body
        code, hd, _ = req(A + "data.csv", headers=auth)
        assert code == 200 and "attachment" in hd["Content-Disposition"]
        assert req(A + "big.webp", headers=auth)[0] == 413
        assert req(A + "%2e%2e/%2e%2e/README.md", headers=auth)[0] == 400
        assert req(A + "..%2F..%2FREADME.md", headers=auth)[0] == 400
        assert req(A + "leak.txt", headers=auth)[0] == 403
        assert req(A + "nope.png", headers=auth)[0] == 404
        assert req(f"{base}/api/artifacts/AB/AB-FIX-999", headers=auth)[0] == 200    # 没有这件：空清单
        # 每件时间线和 diff
        code, _, body = req(f"{base}/api/item/AB/{K}", headers=auth)
        it = json.loads(body)
        assert code == 200 and it["has_diff"] and {"add", "dispatch", "report", "gate_open"} <= {e["event"] for e in it["events"]}
        code, hd, body = req(f"{base}/api/diff/AB/{K}", headers=auth)
        assert code == 200 and "change-" in body and hd["Content-Type"].startswith("text/plain")
        # 项目设置：项目目标
        post = lambda path, b: json.loads(req(base + path, json.dumps(b).encode(), {"Content-Type": "application/json", **auth})[2])
        assert post("/api/goal", {"code": "AB", "goal": "让布艺店主十分钟上架一款新品"})["ok"]
        assert json.load(open(loop.cfg_path("AB")))["goal"] == "让布艺店主十分钟上架一款新品"
        assert not post("/api/goal", {"code": "AB", "goal": "长" * 201})["ok"]
        assert post("/api/goal", {"code": "AB", "goal": ""})["ok"] and "goal" not in json.load(open(loop.cfg_path("AB")))
        # 件页补充反馈：作废旧看效果闸门
        assert post("/api/note", {"code": "AB", "item": K, "words": "按钮再大一点"})["ok"]
        assert gate in loop.state("AB")["superseded_gates"]
    finally:
        p.terminate(); p.wait(5)
    p, base, token = start_panel(loop, {**loop.env, "EVO_AGENT": "muse"})      # 外部 Agent 环境：改不了目标
    try:
        r = json.loads(req(base + "/api/goal", json.dumps({"code": "AB", "goal": "随便改"}).encode(),
                           {"Content-Type": "application/json", "Authorization": f"Bearer {token}"})[2])
        assert not r["ok"] and "外部 Agent" in r["error"]
    finally:
        p.terminate(); p.wait(5)


def test_panel_html_preview_is_sandboxed_without_same_origin():
    page = open(os.path.join(KIT, "panel", "index.html"), encoding="utf-8").read()
    assert 'sandbox="allow-scripts"' in page and "allow-same-origin" not in page
    assert "default-src 'none'" in page and "connect-src 'none'" in page and "srcdoc=" in page
    assert "岗位状态" in page and "卡太久" in page and "没有活路" in page and "时间线" in page and "项目目标" in page


# ---------- 3 首页：岗位状态、卡太久 ----------
def test_status_roles_and_stale(loop):
    loop.project("AB")
    loop.plan(build=["silent"])
    loop.add("AB")
    loop.tick("AB")
    j = loop.status_json("AB")
    roles = {r["role"]: r for r in j["roles"]}
    assert roles["build"]["status"] == "busy" and roles["build"]["label"] == "忙" and roles["build"]["items"] == [K]
    assert roles["verify"]["label"] == "闲"
    assert roles["decide"]["label"] == "暂停" and "没配置" in roles["decide"]["why"]
    assert j["stale"] == []
    loop.env["EVO_NOW"] = at("2026-10-20", "18:30")
    j = loop.status_json("AB")
    assert [x["key"] for x in j["stale"]] == [K] and j["stale"][0]["hours"] >= 6 and j["stale"][0]["raw"] == "building"
    loop.write_global({"limits": {"stale_hours": 12}})
    assert loop.status_json("AB")["stale"] == []


def test_role_shows_quota_full(loop):
    loop.project("AB")
    loop.plan(build=["ratelimit"])
    loop.add("AB")
    loop.tick("AB"); loop.tick("AB")
    roles = {r["role"]: r for r in loop.status_json("AB")["roles"]}
    assert roles["build"]["status"] == "rate_limited" and roles["build"]["label"] == "额度满" and roles["build"]["until"]


# ---------- 4 每件时间线 ----------
def test_timeline_records_whole_life_and_log_cli(loop):
    gate = look_item_verified(loop)
    loop.ok("-p", "AB", "approve", gate, "打回", "按钮太小")
    loop.run_until("AB", state_is("verified"))
    g2 = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "look"][0]["id"]
    loop.ok("-p", "AB", "approve", g2, "通过")
    loop.run_until("AB", state_is("merged"))
    evs = events(loop)
    kinds = [e["event"] for e in evs]
    for k in ("add", "dispatch", "report", "gate_open", "gate_reject", "rework", "gate_approve", "merge", "push", "state"):
        assert k in kinds, (k, kinds)
    rej = next(e for e in evs if e["event"] == "gate_reject")
    assert rej["words"] == "按钮太小" and rej["gate"] == gate                  # 打回原话
    assert "按钮太小" in next(e for e in evs if e["event"] == "rework")["why"]
    merge = next(e for e in evs if e["event"] == "merge")
    assert merge["sha"] == next(e for e in evs if e["event"] == "push")["sha"] == loop.remote_head("AB")
    assert kinds.index("merge") < kinds.index("push")
    tlf = os.path.join(loop.projects, "AB", "state", "timeline.jsonl")       # 每个项目一份、只追加
    assert len(open(tlf).read().splitlines()) == len(evs)
    out = loop.ok("-p", "AB", "log", K).stdout
    assert "gate_reject" in out and "按钮太小" in out
    assert "change-" in loop.ok("-p", "AB", "log", K, "--diff").stdout       # 合并后工作区清理了，看合并提交
    assert loop.evo("-p", "AB", "log", "AB-FIX-999").returncode != 0
    assert loop.evo("-p", "AB", "log", "../etc").returncode != 0


# ---------- 5 新反馈作废旧闸门 ----------
def test_item_feedback_supersedes_open_look_gate(loop):
    gate = look_item_verified(loop)
    r = loop.ok("-p", "AB", "feedback", "--item", K, "颜色太浅，看不清")
    assert "作废" in r.stdout
    st = loop.state("AB"); it = st["items"][K]
    assert gate in st["superseded_gates"] and it["gates"]["look"] != gate and it["state"] == "queued"
    r = loop.evo("-p", "AB", "approve", gate, "通过")                         # 旧闸门上的「通过」不执行
    assert r.returncode != 0 and "已作废" in (r.stdout + r.stderr)
    assert "look_patch" not in loop.item("AB")
    assert not any(g["id"] == gate for g in loop.status_json("AB")["gates"])
    loop.run_until("AB", state_is("verified"))
    assert "颜色太浅，看不清" in builds(loop)[-1]["spec"]
    g2 = [g for g in loop.status_json("AB")["gates"] if g["kind"] == "look"]
    assert len(g2) == 1 and "补充反馈后重看" in g2[0]["question"]
    loop.ok("-p", "AB", "approve", g2[0]["id"], "通过")
    loop.run_until("AB", state_is("merged"))
    assert "gate_superseded" in [e["event"] for e in events(loop)]


def test_item_feedback_supersedes_do_gate(loop):
    loop.project("AB")
    loop.add("AB", "新增布料收藏夹", "web/", ["--product"])
    loop.tick("AB")
    old = loop.status_json("AB")["gates"][0]
    assert old["kind"] == "do"
    loop.ok("-p", "AB", "feedback", "--item", K, "收藏夹要能分组")
    assert loop.evo("-p", "AB", "approve", old["id"], "做").returncode != 0
    new = loop.status_json("AB")["gates"]
    assert len(new) == 1 and new[0]["kind"] == "do" and new[0]["id"] != old["id"] and "补充反馈后" in new[0]["question"]
    loop.tick("AB")
    assert loop.item("AB")["state"] == "queued" and not builds(loop)           # 新闸门没点，照样不开工
    loop.ok("-p", "AB", "approve", new[0]["id"], "做")
    loop.run_until("AB", state_is("merged"))
    assert len(builds(loop)) == 1 and "收藏夹要能分组" in builds(loop)[0]["spec"]


def test_feedback_without_open_gate_is_carried_into_next_rework(loop):
    loop.project("AB")
    loop.plan(build=["silent"])
    loop.add("AB")
    loop.tick("AB")
    r = loop.ok("-p", "AB", "feedback", "--item", K, "提示语别用英文")
    assert "没有等你的闸门" in r.stdout and not loop.state("AB").get("superseded_gates")
    assert "提示语别用英文" in loop.item("AB")["spec"]


def test_trusted_issue_comment_supersedes_but_old_untrusted_and_evo_comments_dont(loop):
    gate = look_item_verified(loop, ["--issue", "7"], github_repo="o/r", trusted_authors=["o"])
    json.dump({"7": [{"id": 1, "user": {"login": "o"}, "body": "开闸门前的旧话", "created_at": "2026-10-20T03:00:00Z"},
                     {"id": 2, "user": {"login": "x"}, "body": "外人说全删了", "created_at": "2026-10-20T04:30:00Z"},
                     {"id": 3, "user": {"login": "o"}, "body": "合并记录 …\n\n<!-- evo -->", "created_at": "2026-10-20T04:31:00Z"},
                     {"id": 4, "user": {"login": "o"}, "body": "字号太小了", "created_at": "2026-10-20T04:32:00Z"}]},
              open(os.path.join(loop.orca_dir, "gh_comments.json"), "w"), ensure_ascii=False)
    loop.ok("-p", "AB", "pull")
    st = loop.state("AB")
    assert gate in st["superseded_gates"]
    assert "字号太小了" in st["items"][K]["spec"]
    assert "外人说全删了" not in st["items"][K]["spec"] and "开闸门前的旧话" not in st["items"][K]["spec"]
    loop.ok("-p", "AB", "pull")                                               # 同一条评论不会再作废一次
    assert len(loop.state("AB")["superseded_gates"]) == 1
    fb = [e for e in events(loop) if e["event"] == "feedback"]
    assert len(fb) == 1 and "issue 评论" in fb[0]["source"]


def test_outside_agent_cannot_supersede_owner_gate(loop):
    gate = look_item_verified(loop)
    loop.env["EVO_AGENT"] = "muse"
    r = loop.evo("-p", "AB", "feedback", "--item", K, "直接通过吧")
    assert r.returncode != 0 and "外部 Agent" in (r.stdout + r.stderr)
    assert not loop.state("AB").get("superseded_gates") and loop.item("AB")["gates"]["look"] == gate


# ---------- 6 项目目标进任务书 ----------
def test_goal_prepended_to_every_spec(loop):
    loop.project("AB")
    loop.ok("-p", "AB", "goal", "set", "让布艺店主十分钟上架一款新品")
    assert loop.status_json("AB")["goal"] == "让布艺店主十分钟上架一款新品"
    loop.plan(verify=["fail"])
    loop.add("AB")
    loop.run_until("AB", state_is("merged"))
    ws = loop.workers()
    assert len(ws) == 4                                                       # 施工、验收（不过）、返工、复验
    for w in ws:
        assert w["spec"].startswith("项目目标：让布艺店主十分钟上架一款新品\n"), w["spec"][:80]
    assert loop.evo("-p", "AB", "goal", "set", "第一行\n第二行\n第三行").returncode != 0
    assert loop.evo("-p", "AB", "goal", "set", "长" * 201).returncode != 0
    loop.env["EVO_AGENT"] = "muse"
    r = loop.evo("-p", "AB", "goal", "set", "外部改的")
    assert r.returncode != 0 and "外部 Agent" in (r.stdout + r.stderr)
    del loop.env["EVO_AGENT"]
    loop.ok("-p", "AB", "goal", "clear")
    assert loop.status_json("AB")["goal"] is None


def test_new_and_import_accept_goal(loop):
    repo = os.path.join(loop.tmp, "repos", "CD")
    os.makedirs(repo); loop.git(repo, "init", "-q", "-b", "main")
    open(os.path.join(repo, "a.txt"), "w").write("a\n"); loop.git(repo, "add", "a.txt"); loop.git(repo, "commit", "-qm", "i")
    loop.ok("import", "CD", "--name", "项目CD", "--path", repo, "--test", "true", "--goal", "给仓库管理员省掉手工对账")
    assert json.load(open(loop.cfg_path("CD")))["goal"] == "给仓库管理员省掉手工对账"
    loop.ok("new", "EF", "--name", "项目EF", "--path", os.path.join(loop.tmp, "repos", "EF"), "--goal", "做一个记账小工具")
    assert json.load(open(loop.cfg_path("EF")))["goal"] == "做一个记账小工具"
    assert loop.evo("new", "GH", "--name", "x", "--path", os.path.join(loop.tmp, "repos", "GH"), "--goal", "长" * 201).returncode != 0
