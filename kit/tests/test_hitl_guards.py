"""借鉴 hitl-dev-loop 的三道检查：JSON 交卷、改动不许越界、git 共享配置守卫。"""
import os

from conftest import state_is


def builds(loop):
    return [w for w in loop.workers() if w["role"] == "build"]


def test_missing_report_triggers_rework(loop):
    loop.project("AB")
    loop.plan(build=["noreport"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"), n=12)
    assert st["items"]["AB-FIX-001"]["round"] == 1
    assert "交卷格式不对" in builds(loop)[1]["spec"]


def test_red_test_in_report_triggers_rework(loop):
    loop.project("AB")
    loop.plan(build=["redtest"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"), n=12)
    assert st["items"]["AB-FIX-001"]["round"] == 1
    assert "make test" in builds(loop)[1]["spec"]


def test_unfinished_report_triggers_rework(loop):
    loop.project("AB")
    loop.plan(build=["unfinished"])
    loop.add("AB")
    loop.run_until("AB", state_is("merged"), n=12)
    assert "还差一半" in builds(loop)[1]["spec"]


def test_blocked_report_goes_to_decider(loop):
    loop.project("AB")
    loop.plan(build=["blocked"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("asking"))
    assert "还差一半" in st["items"]["AB-FIX-001"]["ask"]
    assert not [w for w in loop.workers() if w["role"] == "verify"]


def test_out_of_scope_change_is_never_verified_or_merged(loop):
    loop.project("AB")
    loop.plan(build=["oos"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("escalated"), n=12)
    it = st["items"]["AB-FIX-001"]
    assert "outside-scope.txt" in builds(loop)[1]["spec"]
    assert not [w for w in loop.workers() if w["role"] == "verify"]
    assert "outside-scope.txt" not in loop.git(loop.remote("AB"), "ls-tree", "-r", "--name-only", "main", check=False)
    assert "需要决策" in loop.notifications()


def test_manual_checks_reach_look_gate_and_status(loop):
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))
    item = loop.status_json("AB")["items"][0]
    assert item["manual_checks"] == ["在 1280px 宽度下看注册页"]
    assert "1280px" in loop.notifications()


def test_git_guard_restores_core_worktree(loop):
    loop.project("AB")
    repo = loop.repo("AB")
    loop.add("AB")
    loop.tick("AB")
    elsewhere = os.path.join(loop.tmp, "elsewhere"); os.makedirs(elsewhere)
    loop.git(repo, "config", "core.worktree", elsewhere)
    loop.git(repo, "config", "core.bare", "true")
    st = loop.run_until("AB", state_is("merged"), n=12)
    assert loop.git(repo, "config", "--local", "--get", "core.worktree", check=False) == ""
    assert loop.git(repo, "config", "--local", "--get", "core.bare") == "false"
    assert any("复原了被改动的 git 共享配置" in l for l in st["log"])
