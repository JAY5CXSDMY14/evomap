"""第二十二轮第 5 条：错题本的关单标准——不是「修了」，而是「机制上不可能再发生」。

Mechanism 字段（可选，`kind — 指向`）：kind ∈ code / test / script / gate / hook / static / rule / review，强弱顺序
代码结构 > 静态检查 > 规则/技能 > 靠人审。挪进「已关单」的条目必须有 code/test/script/gate/hook/static 级的机制和指向。
"""
import os, subprocess, sys

from conftest import KIT

HEAD = """# LESSONS

## 活跃教训

### 4. 验证

"""
ENTRY = """### L-{n} {title}
- **Why**: 检查永远不会变红，等于没写。
- **Evidence**: `abc1234` 合成考卷 111 次全绿。
- **Seen**: 1× (2026-10-04)
- **Category**: 验证
{mech}"""


def entry(n="0001", title="判据上线前先喂一个应该变红的输入", mech=""):
    return ENTRY.format(n=n, title=title, mech=mech + "\n" if mech else "")


def lessons(tmp_path, text, *cmd):
    f = tmp_path / "LESSONS.md"
    f.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, os.path.join(KIT, "bin", "lessons.py"), *cmd, "--file", str(f)],
                          capture_output=True, text=True)


def test_mechanism_is_optional_on_active_lessons(tmp_path):
    r = lessons(tmp_path, HEAD + entry(), "lint")
    assert r.returncode == 0, r.stdout


def test_mechanism_kind_must_be_known_and_strong_kinds_need_a_pointer(tmp_path):
    ok = HEAD + entry(mech="- **Mechanism**: test — kit/tests/test_round22.py::test_canary_catches_planted_failures")
    assert lessons(tmp_path, ok, "lint").returncode == 0
    bad = HEAD + entry(mech="- **Mechanism**: vibes — 大家注意")
    r = lessons(tmp_path, bad, "lint")
    assert r.returncode == 1 and "Mechanism" in r.stdout
    nopath = HEAD + entry(mech="- **Mechanism**: gate")
    r = lessons(tmp_path, nopath, "lint")
    assert r.returncode == 1 and "pointer" in r.stdout
    rule = HEAD + entry(mech="- **Mechanism**: rule — kit/roles/verifier.md")
    assert lessons(tmp_path, rule, "lint").returncode == 0


def test_closed_lessons_need_mechanical_closure(tmp_path):
    closed_ok = HEAD + "## 已关单\n\n" + entry(mech="- **Mechanism**: test — kit/tests/test_round22.py")
    assert lessons(tmp_path, closed_ok, "lint").returncode == 0
    for m in ("", "- **Mechanism**: rule — kit/roles/verifier.md", "- **Mechanism**: review — 老板看效果时留意"):
        r = lessons(tmp_path, HEAD + "## 已关单\n\n" + entry(mech=m), "lint")
        assert r.returncode == 1 and "closed" in r.stdout, (m, r.stdout)


def test_stats_reports_mechanism_breakdown(tmp_path):
    text = HEAD + entry("0001", mech="- **Mechanism**: test — kit/tests/x.py") + "\n" + entry("0002", "合并前问远端确认推送成功") + "\n" \
        + entry("0003", "闸门判定不信本地输出只信远端", mech="- **Mechanism**: rule — kit/roles/builder.md")
    r = lessons(tmp_path, text, "stats")
    assert r.returncode == 0
    assert "mechanism: test 1" in r.stdout and "none 1" in r.stdout and "rule 1" in r.stdout
    assert "not yet mechanical: 2" in r.stdout


def test_retro_role_and_template_state_the_closing_standard():
    retro = open(os.path.join(KIT, "roles", "retro.md"), encoding="utf-8").read()
    assert "Mechanism" in retro and "机制上不可能再发生" in retro and "代码结构 > 静态检查 > 规则/技能 > 靠人审" in retro
    tpl = open(os.path.join(KIT, "templates", "project", "docs", "LESSONS.md"), encoding="utf-8").read()
    assert "## 已关单" in tpl and "Mechanism" in tpl
    r = subprocess.run([sys.executable, os.path.join(KIT, "bin", "lessons.py"), "lint", "--file",
                        os.path.join(KIT, "templates", "project", "docs", "LESSONS.md")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
