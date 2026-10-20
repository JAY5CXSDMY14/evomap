"""一件事的完整流水线：施工 → 验收 → [看效果] → 合并 → 推送，以及各种岔路。"""
import glob, json, os

from conftest import state_is


def test_happy_path_merge_and_push(loop):
    loop.project("AB")
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"))
    it = st["items"]["AB-FIX-001"]
    # 推到了裸远端，远端头就是记录的推送提交
    assert it["pushed"] == loop.remote_head("AB")
    assert any(f.startswith("web/change-") for f in loop.remote_files("AB"))
    # 施工和验收换了模型
    assert it["dispatch"]["build"]["model"] != it["dispatch"]["verify"]["model"]
    # 合并前跑过测试；工作区收拾掉了
    assert loop.test_runs("AB") >= 1
    assert not os.path.isdir(it["worktree"])
    s = loop.status_json("AB")
    assert s["items"][0]["state"] == "已合并·可收菜"
    assert "已合并·可收菜" in loop.ok("-p", "AB", "status").stdout


def test_verifier_rejects_then_rework_merges(loop):
    loop.project("AB")
    loop.plan(verify=["fail"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"))
    it = st["items"]["AB-FIX-001"]
    assert it["round"] == 1
    builds = [w for w in loop.workers() if w["role"] == "build"]
    assert len(builds) == 2 and "验收不通过" in builds[1]["spec"]
    assert it["model_i"] == 1                     # 返工换了施工模型
    assert it["pushed"] == loop.remote_head("AB")


def test_rework_limit_escalates_as_stuck(loop):
    loop.project("AB")
    loop.plan(verify=["fail", "fail", "fail"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("escalated"), n=12)
    assert st["items"]["AB-FIX-001"]["round"] == 3
    assert loop.status_json("AB")["stuck"] == 1
    assert "需要决策" in loop.notifications()
    assert len([w for w in loop.workers() if w["role"] == "verify"]) == 3


def test_owner_reject_carries_verbatim_words(loop):
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))
    gates = loop.status_json("AB")["gates"]
    assert len(gates) == 1 and "看效果" in gates[0]["question"]
    loop.ok("-p", "AB", "approve", gates[0]["id"], "打回", "按钮颜色太刺眼")
    it = loop.item("AB")
    assert it["state"] == "queued" and it["round"] == 1
    spec = loop.orca_state()["tasks"][it["build"]]["spec"]
    assert "老板看效果打回：按钮颜色太刺眼" in spec
    loop.run_until("AB", state_is("verified"))
    builds = [w for w in loop.workers() if w["role"] == "build"]
    assert "按钮颜色太刺眼" in builds[-1]["spec"]
    gates = loop.status_json("AB")["gates"]
    assert len(gates) == 1 and "第 1 轮" in gates[0]["question"]
    loop.ok("-p", "AB", "approve", gates[0]["id"], "通过")
    st = loop.run_until("AB", state_is("merged"))
    assert st["items"]["AB-FIX-001"]["pushed"] == loop.remote_head("AB")


def test_remote_ahead_merges_retests_and_pushes_without_force(loop):
    repo = loop.project("AB")
    # 别人先往远端推了一个提交
    other = os.path.join(loop.tmp, "other")
    loop.git(loop.tmp, "clone", "-q", loop.remote("AB"), other)
    open(os.path.join(other, "OTHER.md"), "w").write("x\n")
    loop.git(other, "add", "OTHER.md"); loop.git(other, "commit", "-qm", "other")
    loop.git(other, "push", "-q", "origin", "main")
    theirs = loop.git(other, "rev-parse", "HEAD")
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"))
    head = loop.remote_head("AB")
    assert st["items"]["AB-FIX-001"]["pushed"] == head
    files = loop.remote_files("AB")
    assert "OTHER.md" in files and any(f.startswith("web/change-") for f in files)
    # 没强推：别人的提交还在远端历史里
    loop.git(loop.remote("AB"), "merge-base", "--is-ancestor", theirs, "main")
    assert "merge origin/main" in loop.git(repo, "log", "-3", "--format=%s")
    assert loop.test_runs("AB") >= 2              # 合并前一次 + 并入远端后重跑一次


def test_push_failure_retries_and_notifies_after_three(loop):
    flag = os.path.join(loop.tmp, "PUSH_BROKEN")
    open(flag, "w").close()
    loop.project("AB")
    loop.patch_cfg("AB", push_cmd=f"test ! -f {flag} && git push origin main")
    loop.add("AB")
    loop.run_until("AB", state_is("pushing"))
    st = loop.state("AB")
    while st.get("push_fail", 0) < 3:
        assert "推送连续失败" not in loop.notifications()
        loop.tick("AB"); st = loop.state("AB")
    assert st["items"]["AB-FIX-001"]["state"] == "pushing"
    assert loop.notifications().count("推送连续失败") == 1
    loop.tick("AB")                               # 第 4 次不再重复喊
    assert loop.notifications().count("推送连续失败") == 1
    os.remove(flag)
    st = loop.run_until("AB", state_is("merged"))
    assert st["push_fail"] == 0 and st["items"]["AB-FIX-001"]["pushed"] == loop.remote_head("AB")


def test_dirty_worktree_on_delivery_triggers_rework(loop):
    loop.project("AB")
    loop.plan(build=["dirty"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"), n=10)
    it = st["items"]["AB-FIX-001"]
    assert it["round"] == 1
    assert any("没提交的改动" in l for l in st["log"])
    # 脏的那次没送验收：只有一次验收
    assert len([w for w in loop.workers() if w["role"] == "verify"]) == 1


def test_dirty_after_rework_limit_is_not_sent_to_verify(loop):
    loop.project("AB")
    loop.plan(build=["dirty", "dirty", "dirty"])
    loop.add("AB")
    loop.run_until("AB", state_is("escalated"), n=10)
    assert [w for w in loop.workers() if w["role"] == "verify"] == []


def test_post_verify_change_blocked_by_patch_id(loop):
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    st = loop.run_until("AB", state_is("verified"))
    wt = st["items"]["AB-FIX-001"]["worktree"]
    open(os.path.join(wt, "web", "sneaky.txt"), "w").write("验收后偷偷加的\n")
    loop.git(wt, "add", "web/sneaky.txt"); loop.git(wt, "commit", "-qm", "sneaky")
    gate = loop.status_json("AB")["gates"][0]["id"]
    loop.ok("-p", "AB", "approve", gate, "通过")
    loop.tick("AB")
    it = loop.item("AB")
    assert it["state"] == "escalated"
    assert any("验收后代码又变了" in l for l in loop.state("AB")["log"])
    assert "web/sneaky.txt" not in loop.remote_files("AB")


def test_conflicting_scope_waits_for_earlier_item(loop):
    loop.project("AB")
    loop.add("AB", "修复注册页验证码不刷新", "web/")
    loop.add("AB", "修复注册页提示文字", "web/login")
    loop.tick("AB")
    st = loop.state("AB")
    assert st["items"]["AB-FIX-001"]["state"] == "building"
    assert st["items"]["AB-FIX-002"]["state"] == "queued"
    st = loop.run_until("AB", lambda s: all(i["state"] == "merged" for i in s["items"].values()), n=12)
    assert st["items"]["AB-FIX-002"]["pushed"] == loop.remote_head("AB")


def test_corrupt_state_backed_up_and_paused(loop):
    loop.project("AB")
    loop.add("AB")
    sp = os.path.join(loop.projects, "AB", "state", "state.json")
    open(sp, "w").write("{坏掉了")
    r = loop.evo("-p", "AB", "tick")
    assert r.returncode != 0
    bad = glob.glob(sp + ".bad-*")
    assert len(bad) == 1 and open(bad[0]).read() == "{坏掉了"
    assert "状态文件损坏" in loop.notifications()
    # 下一轮也不能当成空项目从零开始
    r = loop.evo("-p", "AB", "tick")
    assert r.returncode != 0 and "暂停" in (r.stderr + r.stdout)
    assert not os.path.exists(sp)
    loop.ok("-p", "AB", "resume")
    loop.tick("AB")
    assert os.path.exists(sp)


def test_fetch_failure_is_retried_not_escalated(loop):
    loop.project("AB")
    loop.add("AB")
    loop.run_until("AB", state_is("verifying"))   # 下一轮收验收结果 → 合并 → 推送
    loop.git(loop.repo("AB"), "remote", "set-url", "origin", "/nonexistent/remote.git")
    loop.tick("AB")
    st = loop.state("AB")
    assert st["items"]["AB-FIX-001"]["state"] == "pushing" and st["push_fail"] == 1
    assert any("拉取远端失败" in l for l in st["log"])
    loop.git(loop.repo("AB"), "remote", "set-url", "origin", loop.remote("AB"))
    st = loop.run_until("AB", state_is("merged"))
    assert st["items"]["AB-FIX-001"]["pushed"] == loop.remote_head("AB")


def test_red_after_merging_remote_is_retested_before_retry_push(loop):
    # 远端带进来一个 RED.md：本件工作区里没有它（合并前测试绿），并入远端后才红；放 GREEN 标记后转绿
    green = os.path.join(loop.tmp, "GREEN")
    loop.project("AB", test_cmd=f"test ! -f RED.md || test -f {green}")
    loop.add("AB")
    loop.run_until("AB", state_is("verifying"))   # 下一轮收验收结果 → 合并 → 推送
    other = os.path.join(loop.tmp, "other")
    loop.git(loop.tmp, "clone", "-q", loop.remote("AB"), other)
    open(os.path.join(other, "RED.md"), "w").write("x\n")
    loop.git(other, "add", "RED.md"); loop.git(other, "commit", "-qm", "red")
    loop.git(other, "push", "-q", "origin", "main")
    theirs = loop.remote_head("AB")
    loop.tick("AB")                                   # 本地合并（绿）→ 并入远端 → 红 → 不推
    st = loop.state("AB")
    assert st["items"]["AB-FIX-001"]["state"] == "pushing" and st["push_fail"] == 1
    assert loop.remote_head("AB") == theirs
    loop.tick("AB")                                   # 重试：远端已是祖先，但仍要重测，还是红 → 不推
    st = loop.state("AB")
    assert st["push_fail"] == 2 and loop.remote_head("AB") == theirs
    open(green, "w").close()
    st = loop.run_until("AB", state_is("merged"))
    assert st["items"]["AB-FIX-001"]["pushed"] == loop.remote_head("AB")
    loop.git(loop.remote("AB"), "merge-base", "--is-ancestor", theirs, "main")
