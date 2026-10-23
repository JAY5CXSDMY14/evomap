"""10-23 EV-CHORE-001：--scope 写成一整句中文说明，被当成一条 scope，范围检查把要删的文件全判越界。
现在：scope 按逗号/顿号/分号/空白拆开，只留路径；说明文字挪进任务书；一条路径都读不出就拒绝登记。"""
from conftest import EVO  # noqa: F401


def test_prose_scope_is_split_into_paths(loop):
    loop.project("AB")
    loop.add("AB", title="清理探针残留",
             scope="删除 notes/r20-probe.md、notes/r20-rework.md、artifacts/EV-DOC-004/；只删这些，不碰别的文件")
    it = loop.item("AB")
    assert it["scope"] == ["notes/r20-probe.md", "notes/r20-rework.md", "artifacts/EV-DOC-004/"]


def test_plain_and_chinese_dir_paths_kept(loop):
    loop.project("AB")
    loop.add("AB", scope="web/, docs/说明.md，kit/bin")
    assert loop.item("AB")["scope"] == ["web/", "docs/说明.md", "kit/bin"]


def test_scope_without_any_path_is_refused(loop):
    loop.project("AB")
    r = loop.evo("-p", "AB", "add", "--kind", "fix", "--title", "随便改改", "--scope", "只改文档，不碰代码")
    assert r.returncode != 0 and "scope" in (r.stdout + r.stderr)
    import os
    st = os.path.join(loop.projects, "AB", "state", "state.json")
    assert not os.path.exists(st) or not loop.state("AB").get("items")
