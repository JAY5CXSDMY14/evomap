"""第二十二轮第 3 条：规则注入硬上限。

量的是「最胖」的一份任务书：项目目标写满 200 字、evo 自维护规矩、UI 预设 + 架构预设两段都拼上，再加 Multica 交卷尾巴；
决策岗量一批只有一件时的批次任务书（规则 + 目标 + 固定说明 + 交卷尾巴，件越多越长的那部分不算）。
单位是 UTF-8 字节。上限 = 第二十二轮实测 + 约 20% 余量，见 kit/README.md 第二十二轮。超了别调上限：删一条再加一条。
"""
import json, os, sys

from conftest import KIT
from test_arch_preset import TB_LIKE, commit

sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_exec  # noqa: E402

WORKER = os.path.join(KIT, "tests", "fakes", "worker.py")
# 第二十二轮实测（字节）：施工 13158、验收 11211、决策 6617；岗位文件 builder 4409、verifier 4334、decider 5326、retro 2109。上限 ≈ 实测 × 1.2
CAPS = {"build": 15800, "verify": 13500, "decide": 8000}
ROLE_FILE_CAPS = {"builder.md": 5300, "verifier.md": 5200, "decider.md": 6400, "retro.md": 2550}
HINT = "规则注入超上限：删一条再加一条（不要调高上限）"


def nbytes(t):
    return len(t.encode("utf-8"))


def fattest_specs(loop):
    with_decider(loop)
    repo = loop.project("AB", goal="长" * 200, ui_preset="web-react", arch_preset="python-fastapi", self_maintained=True)
    commit(loop, repo, TB_LIKE)
    loop.ok("-p", "AB", "add", "--kind", "feat", "--title", "新增上架表单和接口", "--scope", "web/src/components/,api/", "--look")
    return loop.item("AB")


def with_decider(loop):
    loop.write_global({"roles": {"decide": {"cmd": f"{sys.executable} {WORKER} decide", "models": ["model-x"],
                                            "prompt": "roles/decider.md", "boot_seconds": 0}},
                       "limits": {"rework_rounds": 0, "decide_every_minutes": 0}})


def test_role_files_under_cap():
    for f, cap in ROLE_FILE_CAPS.items():
        n = nbytes(open(os.path.join(KIT, "roles", f), encoding="utf-8").read())
        assert n <= cap, f"{f} {n} 字节 > {cap}：{HINT}"


def test_assembled_build_and_verify_prompts_under_cap(loop):
    it = fattest_specs(loop)
    b, v = it["build_spec"], it["verify_spec"]
    assert "UI 规范（预设" in b and "架构规范（预设" in b and "evo 自维护规矩" in b       # 确实是最胖的那份
    nb = nbytes(b) + nbytes(evo_exec.BUILD_TAIL)
    nv = nbytes(v) + nbytes(evo_exec.VERIFY_TAIL)
    print(f"build {nb} verify {nv}")
    assert nb <= CAPS["build"], f"施工任务书 {nb} 字节 > {CAPS['build']}：{HINT}"
    assert nv <= CAPS["verify"], f"验收任务书 {nv} 字节 > {CAPS['verify']}：{HINT}"


def test_assembled_decide_prompt_under_cap(loop):
    fattest_specs(loop)
    loop.plan(build=["fail"])
    for _ in range(8):
        loop.tick("AB")
        if any(w["role"] == "decide" for w in loop.workers()):
            break
    d = [w["spec"] for w in loop.workers() if w["role"] == "decide"]
    assert d, "决策岗没被叫醒"
    n = nbytes(d[0]) + nbytes(evo_exec.DECIDE_TAIL)
    print(f"decide {n}")
    assert n <= CAPS["decide"], f"决策岗批次任务书 {n} 字节 > {CAPS['decide']}：{HINT}"
