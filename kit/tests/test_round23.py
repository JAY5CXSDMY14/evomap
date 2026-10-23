"""第二十三轮：Multica 下「施工模型 ≠ 验收模型」的保护（issue #15）。

模型绑在 Multica agent 上（multica.agents.build / verify），evo 每轮派工前读两个 agent 的模型：
相同 → 停派施工 / 验收、推老板一次；不同 → 照常派；读不到 → 默认也停，multica.allow_unverified_models: true 才放行。
假 multica 的 agent 模型字段形状是假设（真机待核实），见 kit/tests/fakes/multica。
"""
import json, os

from conftest import state_is


def set_models(loop, **by_name):
    d = os.path.join(loop.orca_dir, "multica")
    os.makedirs(d, exist_ok=True)
    json.dump(by_name, open(os.path.join(d, "agent-models.json"), "w", encoding="utf-8"), ensure_ascii=False)


def issues(loop):
    return list(loop.multica_state()["issues"].values())


def test_same_model_stops_dispatch_pushes_once_then_resumes(loop):
    loop.multica_project("MB")
    set_models(loop, **{"施工-DSH": "Sonnet", "验收-Claude": "sonnet"})     # 不分大小写：同一个
    loop.add("MB")
    loop.tick("MB"); loop.tick("MB")
    assert loop.item("MB")["state"] == "queued" and not issues(loop)            # 不派施工
    assert loop.notifications().count('"code": "same_model"') == 1                # 只推一次
    assert "施工和验收撞模型" in loop.notifications()
    out = loop.ok("-p", "MB", "status").stdout
    assert "停派施工 / 验收" in out and "同一个模型" in out
    sj = loop.status_json("MB")
    assert sj["model_guard"]["ok"] is False and sj["model_guard"]["code"] == "same_model"
    assert sj["items"][0]["state"] == "等换模型"
    set_models(loop, **{"施工-DSH": "deepseek-official/group/free-ds", "验收-Claude": "sonnet"})
    loop.run_until("MB", state_is("merged"))
    assert loop.status_json("MB")["model_guard"]["ok"] is True


def test_different_models_dispatch_normally(loop):
    loop.multica_project("MB")
    loop.add("MB")
    loop.run_until("MB", state_is("merged"))
    g = loop.status_json("MB")["model_guard"]
    assert g["ok"] is True and g["code"] is None
    assert g["build"] == "deepseek-official/group/free-ds" and g["verify"] == "sonnet"
    assert "撞模型" not in loop.notifications()


def test_group_names_differ_counts_as_different(loop):
    # magpie 组名展不开：名字不同按「不同」处理（假设，见 evo_exec.MulticaExecutor.model_guard）
    loop.multica_project("MB")
    set_models(loop, **{"施工-DSH": "group/evo-build", "验收-Claude": "group/evo-verify"})
    loop.add("MB")
    loop.run_until("MB", state_is("merged"))


def test_unreadable_model_stops_by_default(loop):
    loop.multica_project("MB")
    set_models(loop, **{"验收-Claude": None})
    loop.add("MB")
    loop.tick("MB"); loop.tick("MB")
    assert loop.item("MB")["state"] == "queued" and not issues(loop)
    assert loop.notifications().count('"code": "unverified_model"') == 1           # 只推一次
    g = loop.status_json("MB")["model_guard"]
    assert g["ok"] is False and g["code"] == "unverified_model" and "allow_unverified_models" in g["why"]


def test_unreadable_model_with_allow_dispatches(loop):
    loop.multica_project("MB")
    loop.patch_cfg("MB", multica={"project": "MB", "app_url": "http://multica.test", "allow_unverified_models": True})
    set_models(loop, **{"施工-DSH": None})
    loop.add("MB")
    loop.run_until("MB", state_is("merged"))
    g = loop.status_json("MB")["model_guard"]
    assert g["ok"] is True and g["code"] == "unverified_model"
    assert "已停派工" not in loop.notifications()                                # 显式放行：不推


def test_allow_must_be_literal_true(loop):
    loop.multica_project("MB")
    loop.patch_cfg("MB", multica={"project": "MB", "app_url": "http://multica.test", "allow_unverified_models": "yes"})
    set_models(loop, **{"施工-DSH": None})
    loop.add("MB")
    loop.tick("MB")
    assert loop.item("MB")["state"] == "queued" and not issues(loop)


def test_model_only_in_agent_get_is_read(loop):
    loop.multica_project("MB")
    d = os.path.join(loop.orca_dir, "multica"); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "agent-models-in-get"), "w").close()
    loop.add("MB")
    loop.run_until("MB", state_is("merged"))
    assert loop.status_json("MB")["model_guard"]["verify"] == "sonnet"
    assert any(c[:2] == ["agent", "get"] for c in loop.multica_state()["calls"])


def test_same_agent_for_build_and_verify_stops(loop):
    loop.multica_project("MB")
    loop.patch_cfg("MB", multica={"project": "MB", "app_url": "http://multica.test", "allow_unverified_models": True,
                                  "agents": {"build": "验收-Claude", "verify": "验收-Claude"}})
    loop.add("MB")
    loop.tick("MB")
    assert loop.item("MB")["state"] == "queued" and not issues(loop)
    assert loop.status_json("MB")["model_guard"]["code"] == "same_agent"


def test_orca_project_has_no_model_guard(loop):
    loop.project("MA")
    loop.add("MA")
    loop.tick("MA")
    assert loop.status_json("MA")["model_guard"] is None
