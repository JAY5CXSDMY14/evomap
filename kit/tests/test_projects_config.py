"""多项目、配置拆分、命名规则、错题本、安装脚本。"""
import json, os, subprocess, sys

from conftest import KIT, state_is, sh

PROJECT_KEYS = {"code", "name", "repo", "main_branch", "github_repo", "trusted_authors", "test_cmd", "push_cmd", "deploy_cmd",
                "policy_terms", "lessons_file", "standards_file", "digest_issue"}


def test_two_projects_share_global_builder_cap(loop):
    loop.write_global({"limits": {"builders_total": 1}})
    loop.project("AA"); loop.project("BB")
    loop.add("AA"); loop.add("BB")
    loop.tick("AA")
    assert loop.item("AA")["state"] == "building"
    loop.tick("BB")
    assert loop.item("BB")["state"] == "queued"           # 整机只许 1 路
    loop.tick("AA")                                       # AA 交付 → 不再占施工位
    assert loop.item("AA")["state"] != "building"
    loop.tick("BB")
    assert loop.item("BB")["state"] == "building"


def test_project_cannot_raise_global_cap(loop):
    loop.write_global({"limits": {"builders_total": 1}})
    loop.project("AA", overrides={"limits": {"builders": 5, "builders_total": 9}})
    loop.add("AA", "修复注册页验证码不刷新", "web/")
    loop.add("AA", "修复设置页保存失败", "api/")
    loop.tick("AA")
    states = sorted(i["state"] for i in loop.state("AA")["items"].values())
    assert states == ["building", "queued"]


def test_title_rules(loop):
    loop.project("AB")
    for title, why in [("注册页改版草案", "草案"), ("修复登录页 v2", "版本"), ("修" * 25, "超过 24 字"),
                       ("AB-FIX-001 修复登录", "件号")]:
        r = loop.evo("-p", "AB", "add", "--title", title, "--scope", "web/")
        assert r.returncode != 0 and "标题不合规范" in (r.stderr + r.stdout), title
        assert why in (r.stderr + r.stdout), (title, r.stderr)
    assert not os.path.exists(os.path.join(loop.projects, "AB", "state", "state.json")) or not loop.state("AB")["items"]
    loop.add("AB", "修复注册页验证码不刷新")
    assert list(loop.state("AB")["items"]) == ["AB-FIX-001"]


def test_new_and_import_write_only_project_config(loop):
    path = os.path.join(loop.tmp, "fresh")
    loop.ok("new", "NW", "--name", "新项目", "--path", path)
    c = json.load(open(loop.cfg_path("NW")))
    assert set(c) <= PROJECT_KEYS, set(c) - PROJECT_KEYS
    assert c["push_cmd"] == "" and c["repo"] == path        # 没有远端：只在本地合并
    assert os.path.exists(os.path.join(path, "docs", "LESSONS.md"))
    loop.project("IM")
    c = json.load(open(loop.cfg_path("IM")))
    assert set(c) <= PROJECT_KEYS and c["push_cmd"] == "git push origin main"
    assert "土布" not in json.dumps(c, ensure_ascii=False)


def test_legacy_project_config_with_global_keys_still_works(loop):
    loop.project("LG")
    # 老格式：项目 config 里直接带 limits/notify（视为本项目覆盖）
    loop.patch_cfg("LG", limits={"builders": 2, "owner_queue_pause": 5, "rework_rounds": 0, "stall_minutes": 15},
                   notify={"macos": False, "telegram_bot_token_env": "TUBU_TG_TOKEN", "telegram_chat_id_env": "TUBU_TG_CHAT"})
    loop.plan(verify=["fail"])
    loop.add("LG")
    loop.run_until("LG", state_is("escalated"))           # rework_rounds=0：第一次不过就交决策岗
    assert "需要决策" in loop.notifications()             # 老变量名配置 + 只设了新变量：照样记（交决策岗只进 outbox，不推）


def test_overrides_section_beats_global(loop):
    loop.project("OV", overrides={"limits": {"rework_rounds": 0}})
    loop.plan(verify=["fail"])
    loop.add("OV")
    loop.run_until("OV", state_is("escalated"))


def test_old_telegram_env_names_fallback(loop):
    for k in ("EVO_TG_TOKEN", "EVO_TG_CHAT"):
        loop.env.pop(k)
    loop.env.update(TUBU_TG_TOKEN="oldtok", TUBU_TG_CHAT="oldchat")
    loop.project("AB")
    loop.add("AB")
    loop.env["FAKE_WORKER_STATUS"] = "dead"               # 工人进程不在了 → 卡住，是要推的事
    loop.tick("AB")
    sent = [r for r in loop.http_log() if r["url"].endswith("/sendMessage")]
    assert sent and all("/botoldtok/" in r["url"] for r in sent)
    assert loop.telegram_sent()[0]["chat_id"] == "oldchat" and "疑似卡住" in loop.telegram_sent()[0]["text"]


def test_status_overview_lists_all_projects(loop):
    loop.project("AA"); loop.project("BB")
    out = loop.ok("status").stdout
    assert "AA" in out and "BB" in out
    assert "AA" in loop.ok("projects").stdout


# ---------- 错题本 ----------
GOOD = """# LESSONS
## 活跃教训
### 1. 读懂报告
### L-0001 先在报告人用的界面上原样复现再说修好了
- **Why**: 只修截图里的场景，其它入口仍坏。
- **Evidence**: #834 返工 4 次：`abc1234`。
- **Do**: 复现步骤写进测试。
- **Seen**: 2× (2026-10-05, 2026-10-07)
- **Category**: 读懂报告
"""
BAD = """## 活跃教训
### L-0002 注意
- **Why**: x
- **Evidence**: 没有证据
- **Seen**: 3× (2026-10-05)
### L-0002 重复的编号也要被抓出来
- **Why**: y
- **Evidence**: `deadbee`
- **Seen**: 1× (2026-10-01)
- **Category**: 验证
"""


def lessons(tmp_path, text, *cmd):
    f = tmp_path / "L.md"; f.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, os.path.join(KIT, "bin", "lessons.py"), *cmd, "--file", str(f)],
                          capture_output=True, text=True)


def test_lessons_lint_good(tmp_path):
    r = lessons(tmp_path, GOOD, "lint")
    assert r.returncode == 0, r.stdout
    assert "1 lessons, 0 problems" in r.stdout


def test_lessons_lint_bad(tmp_path):
    r = lessons(tmp_path, BAD, "lint")
    assert r.returncode == 1
    for msg in ("missing **Category**", "Seen says 3×", "Evidence needs", "actionable", "duplicate id"):
        assert msg in r.stdout, (msg, r.stdout)


def test_lessons_category_heading_ends_entry(tmp_path):
    # 一条缺 Category 的教训，后面紧跟分类小标题和不属于它的字段：仍要报缺 Category
    text = GOOD.replace("- **Category**: 读懂报告\n", "") + "### 2. 修一类不修一例\n- **Category**: 游离字段\n"
    r = lessons(tmp_path, text, "lint")
    assert r.returncode == 1 and "missing **Category**" in r.stdout


def test_lessons_template_lints_clean():
    r = subprocess.run([sys.executable, os.path.join(KIT, "bin", "lessons.py"), "lint", "--file",
                        os.path.join(KIT, "templates", "project", "docs", "LESSONS.md")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_lessons_promote(tmp_path):
    r = lessons(tmp_path, GOOD.replace("2× (2026-10-05, 2026-10-07)", "3× (2026-10-05, 2026-10-07, 2026-10-09)"), "promote")
    assert "L-0001 Seen 3×" in r.stdout


# ---------- 安装脚本 ----------
def test_install_check_only_changes_nothing_then_apply_is_idempotent(loop):
    home = loop.env["HOME"]
    inst = os.path.join(KIT, "install.sh")
    r = subprocess.run(["bash", inst], env=loop.env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "只检查" in r.stdout and not os.path.exists(os.path.join(home, ".evoloop"))
    r = subprocess.run(["bash", inst, "--apply", "--link"], env=loop.env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    g = os.path.join(home, ".evoloop", "config.json")
    assert json.load(open(g))["limits"]["builders_total"] == 2
    assert os.path.realpath(os.path.join(home, ".local", "bin", "evo")) == os.path.join(KIT, "bin", "evo")
    assert "evo new" in r.stdout and "evo import" in r.stdout
    calls = json.load(open(os.path.join(loop.orca_dir, "state.json")))["calls"]
    assert ["skills", "install"] in calls and ["repo", "add"] not in calls     # 装了技能，但不登记项目
    open(g, "w").write('{"nightly_at": "22:00"}')
    r = subprocess.run(["bash", inst, "--apply", "--link"], env=loop.env, capture_output=True, text=True)
    assert r.returncode == 0 and "不覆盖" in r.stdout
    assert json.load(open(g)) == {"nightly_at": "22:00"}
