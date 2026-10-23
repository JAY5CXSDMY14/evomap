"""第十六轮：App ↔ evo 的 JSON 接口定版本（schema_version + kit/schemas/ 校验）。插件机制第二十四轮删了（#16）。"""
import json, os, sys

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from conftest import KIT, state_is

SCHEMAS = os.path.join(KIT, "schemas")
sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_rt as RT  # noqa: E402


def _registry():
    res = []
    for f in os.listdir(SCHEMAS):
        d = json.load(open(os.path.join(SCHEMAS, f), encoding="utf-8"))
        res.append((d["$id"], Resource.from_contents(d)))
    return Registry().with_resources(res)


REG = _registry()


def check(schema, doc):
    s = json.load(open(os.path.join(SCHEMAS, schema), encoding="utf-8"))
    v = Draft202012Validator(s, registry=REG)
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    assert not errs, f"{schema}: " + "; ".join(f"{list(e.path)} {e.message}" for e in errs[:5])
    return doc


def js(r):
    return json.loads(r.stdout)


# ---------- 一、接口定版本 ----------

def test_all_schemas_are_valid_draft2020():
    for f in os.listdir(SCHEMAS):
        d = json.load(open(os.path.join(SCHEMAS, f), encoding="utf-8"))
        Draft202012Validator.check_schema(d)
        assert d["$id"].endswith(f)


def test_app_json_outputs_match_schemas(loop):
    """App 调的每个 --json：顶层 schema_version=1，且符合 kit/schemas/。"""
    loop.project("AB")
    loop.add("AB")
    loop.run_until("AB", state_is("merged"))
    pj = check("projects.schema.json", js(loop.ok("projects", "--json")))
    assert pj["schema_version"] == 1 and [p["code"] for p in pj["projects"]] == ["AB"]
    assert pj["projects"][0]["name"] == "项目AB"
    st = check("status.schema.json", loop.status_json("AB"))
    assert st["schema_version"] == 1
    key = st["items"][0]["key"]
    lg = check("log.schema.json", js(loop.ok("-p", "AB", "log", key, "--json")))
    assert lg["schema_version"] == 1 and lg["events"]
    tm = check("team.schema.json", js(loop.ok("team", "--json")))
    assert tm["schema_version"] == 1
    ti = check("team-init.schema.json", js(loop.ok("team", "init", "--json")))
    assert ti["schema_version"] == 1


def test_other_json_outputs_carry_schema_version(loop):
    loop.project("AB")
    assert js(loop.ok("models", "--json"))["schema_version"] == 1
    assert js(loop.ok("-p", "AB", "ui", "show", "--json"))["schema_version"] == 1
    assert js(loop.ok("-p", "AB", "arch", "show", "--json"))["schema_version"] == 1


def test_projects_text_output_unchanged(loop):
    """老 App（和 ProjectList.parse）还读纯文本：不带 --json 的输出不变。"""
    loop.project("AB")
    out = loop.ok("projects").stdout
    assert out.split()[0] == "AB" and not out.lstrip().startswith("{")


# ---------- 功能包的版本范围语法（原来插件和功能包各一份，第二十四轮只留 evo_rt 这份）----------

def test_api_range_syntax():
    m = lambda s: RT.api_matches(s, (1, 0))
    assert m("^1") and m("1") and m(">=1 <2") and m(">=1.0,<3")
    assert m("*") and m("~1.0")
    assert not m("^2") and not m(">1") and not m("<1")
    with pytest.raises(ValueError):
        m("latest")


def test_plugin_command_is_gone(loop):
    """第二十四轮（#16）：evo plugin 子命令和 ~/.evoloop/plugins 都不再有。"""
    r = loop.evo("plugin", "list", "--json")
    assert r.returncode != 0
    assert not os.path.exists(os.path.join(KIT, "bin", "evo_plugin.py"))
    assert not os.path.exists(os.path.join(KIT, "features", "plugins"))
