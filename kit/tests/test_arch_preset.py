"""第十五轮：后端 / 架构预设（kit/presets/arch）。项目配置 arch_preset / arch_overrides、evo arch show|set|check、
new/import --arch-preset、碰后端路径的件任务书里带「架构规范」、交卷时结构检查（约定外新目录 / 向上依赖 / 下层用 Web 框架 /
禁用库 / 迁移命名与编号 / 写死口令打回，其余只提示）、现有结构优先且只报一次、外部工具只算新增且没装只警告、ST 用 swift-app、TB 不动。"""
import json, os, shutil, sys

import pytest

from conftest import KIT, state_is

sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_arch as A  # noqa: E402

K = "AB-FIX-001"
UI_SPIRIT = ["优先复用成熟库和成熟做法", "统一规范", "严格限制重复依赖", "不重复造轮子"]
ARCH_EXTRA = ["依赖方向单向", "按领域分包", "配置走环境变量"]


def events(loop, key=K):
    return json.loads(loop.ok("-p", "AB", "log", key, "--json").stdout)["events"]


def commit(loop, repo, files, msg="c"):
    for rel, text in files.items():
        p = os.path.join(repo, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(text)
        loop.git(repo, "add", rel)
    loop.git(repo, "commit", "-qm", msg)
    loop.git(repo, "push", "-q", "origin", "main", check=False)
    return loop.git(repo, "rev-parse", "HEAD")


TB_LIKE = {"api/__init__.py": "", "api/main.py": "from api.routers import items\n", "api/config.py": "import os\nDSN = os.getenv('DATABASE_URL')\n",
           "api/db.py": "from api import config\n", "api/items_repo.py": "from api import db\n", "api/search_service.py": "from api import items_repo\n",
           "api/routers/__init__.py": "", "api/routers/items.py": "from fastapi import APIRouter\nfrom api import items_repo\n",
           "api/tests/__init__.py": "", "migrations/001_init.sql": "--\n", "migrations/002_items.sql": "--\n",
           "requirements.txt": "fastapi>=0.115\npsycopg[binary]>=3.2\nhttpx2>=2\npytest>=8\n"}


# ---------- 1 预设文件 ----------
def test_preset_files_have_principles_folders_layers_rules_checks():
    assert A.load_preset("none") is None
    with pytest.raises(ValueError):
        A.load_preset("django")
    for name in ("python-fastapi", "node-ts", "swift-app"):
        pre = A.load_preset(name)
        assert pre["principles"] == UI_SPIRIT + ARCH_EXTRA, name
        assert pre["folders"] and pre["layers"] and pre["rules"] and pre["checks"] and pre["sources"]
        assert all(s["url"].startswith("https://") and s["license"] and s["take"] for s in pre["sources"])
        assert pre["checks"][0]["id"] == "builtin"
        for c in pre["categories"].values():
            assert c["label"] and c["choice"] and c["source"] in ("owner", "suggested") and isinstance(c["banned"], list)
        assert any(r.startswith("红线") and "ask 决策岗" in r and "ADR" in r for r in pre["rules"])
        assert any(r.startswith("只管新写的代码") for r in pre["rules"])
    py = A.load_preset("python-fastapi")
    ck = {c["id"]: c for c in py["checks"]}
    assert "pip install import-linter" in ck["import-linter"]["install"] and "pip install ruff" in ck["ruff"]["install"]
    assert [l["name"] for l in py["layers"]] == ["entry", "api", "service", "repository", "core"]
    assert "fastapi" in next(l for l in py["layers"] if l["name"] == "repository")["forbid_imports"]
    assert "requests" in py["categories"]["http"]["banned"] and "flake8" in py["categories"]["lint"]["banned"]
    node = A.load_preset("node-ts")
    assert "express" in next(l for l in node["layers"] if l["name"] == "domain")["forbid_imports"]
    assert {c["id"] for c in node["checks"]} == {"builtin", "dependency-cruiser"}
    sw = A.load_preset("swift-app")
    assert "SwiftUI" in next(l for l in sw["layers"] if l["name"] == "domain")["forbid_imports"] and "Alamofire" in sw["categories"]["networking"]["banned"]
    readme = open(os.path.join(KIT, "presets", "arch", "README.md"), encoding="utf-8").read()
    assert all(p in readme for p in UI_SPIRIT + ARCH_EXTRA) and "TB" in readme and "第十五轮" in readme and "arch_overrides" in readme


def test_madr_vendored():
    vd = os.path.join(KIT, "vendor", "madr")
    for f in ("LICENSE", "LICENSE.MIT", "VENDOR.md", "template/adr-template-minimal.md", "template/adr-template.md"):
        assert os.path.exists(os.path.join(vd, f)), f
    v = open(os.path.join(vd, "VENDOR.md"), encoding="utf-8").read()
    assert "ba75bb1" in v and "MIT OR CC0-1.0" in v


# ---------- 2 配置与命令 ----------
def test_default_none_adds_nothing_and_arch_set_show(loop):
    loop.project("AB")
    assert "none" in loop.ok("-p", "AB", "arch").stdout and loop.status_json("AB")["arch_preset"] == "none"
    loop.add("AB", "加接口", "src/")
    loop.tick("AB")
    assert all("架构规范" not in w["spec"] for w in loop.workers())
    loop.ok("-p", "AB", "arch", "set", "python-fastapi")
    assert json.load(open(loop.cfg_path("AB")))["arch_preset"] == "python-fastapi"
    out = loop.ok("-p", "AB", "arch", "show").stdout
    assert "import-linter" in out and "不另加" in out and "依赖方向单向" in out and "源码根：src/" in out
    loop.ok("-p", "AB", "arch", "set", "allow_dirs=src/jobs,scripts/ops")
    loop.ok("-p", "AB", "arch", "set", "deps.http=requests")
    loop.ok("-p", "AB", "arch", "set", r"migrations_pattern=^\d{3}_[a-z_]+\.sql$")
    ov = json.load(open(loop.cfg_path("AB")))["arch_overrides"]
    assert ov["allow_dirs"] == ["src/jobs", "scripts/ops"] and ov["deps.http"] == ["requests"] and ov["migrations_pattern"].startswith("^")
    eff = json.loads(loop.ok("-p", "AB", "arch", "--json").stdout)["effective"]
    assert "httpx*" in eff["categories"]["http"]["banned"] and "requests" not in eff["categories"]["http"]["banned"]
    for k in ("allow_dirs", "deps.http", "migrations_pattern"):
        loop.ok("-p", "AB", "arch", "set", k + "=")
    assert "arch_overrides" not in json.load(open(loop.cfg_path("AB")))
    assert loop.evo("-p", "AB", "arch", "set", "django").returncode != 0
    assert loop.evo("-p", "AB", "arch", "set", "root=$(rm -rf ~)").returncode != 0
    assert loop.evo("-p", "AB", "arch", "set", "evil=1").returncode != 0
    assert loop.evo("-p", "AB", "arch", "set", "layout=hexagon").returncode != 0
    assert loop.evo("-p", "AB", "arch", "set", "migrations_pattern=([").returncode != 0
    loop.env["EVO_AGENT"] = "muse"
    r = loop.evo("-p", "AB", "arch", "set", "node-ts")
    assert r.returncode != 0 and "外部 Agent" in (r.stdout + r.stderr)
    assert loop.evo("-p", "AB", "arch", "show").returncode == 0
    del loop.env["EVO_AGENT"]
    loop.ok("-p", "AB", "arch", "set", "none")
    assert "arch_preset" not in json.load(open(loop.cfg_path("AB")))


def test_new_and_import_accept_arch_preset(loop):
    repo = os.path.join(loop.tmp, "repos", "CD")
    os.makedirs(repo); loop.git(repo, "init", "-q", "-b", "main")
    for rel, t in TB_LIKE.items():
        p = os.path.join(repo, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(t)
    loop.git(repo, "add", "-A"); loop.git(repo, "commit", "-qm", "i")
    r = loop.ok("import", "CD", "--name", "项目CD", "--path", repo, "--test", "true", "--arch-preset", "python-fastapi")
    assert json.load(open(loop.cfg_path("CD")))["arch_preset"] == "python-fastapi"
    assert "沿用现有" in r.stdout and "api/" in r.stdout and "migrations/" in r.stdout      # 导入时就把现有结构说一次
    loop.ok("new", "EF", "--name", "项目EF", "--path", os.path.join(loop.tmp, "repos", "EF"), "--arch-preset", "node-ts")
    assert json.load(open(loop.cfg_path("EF")))["arch_preset"] == "node-ts"
    loop.ok("new", "GH", "--name", "项目GH", "--path", os.path.join(loop.tmp, "repos", "GH"))
    assert "arch_preset" not in json.load(open(loop.cfg_path("GH")))
    assert loop.evo("new", "IJ", "--name", "x", "--path", os.path.join(loop.tmp, "repos", "IJ"), "--arch-preset", "rails").returncode != 0
    assert not os.path.exists(os.path.join(loop.tmp, "repos", "IJ"))


# ---------- 3 任务书注入 ----------
def test_arch_block_only_for_backend_scope_and_after_goal_and_ui(loop):
    repo = loop.project("AB", goal="让布艺店主十分钟上架一款新品", arch_preset="python-fastapi", ui_preset="web-react")
    commit(loop, repo, TB_LIKE)
    loop.add("AB", "新增材料搜索接口", "api/")                                   # 后端
    loop.ok("-p", "AB", "add", "--kind", "ux", "--title", "改版首页", "--scope", "web/src/components/")   # 只碰界面
    loop.ok("-p", "AB", "add", "--kind", "feat", "--title", "加一张迁移", "--scope", "migrations/")       # 迁移目录也算后端
    st = loop.state("AB")["items"]
    b, v = st[K]["build_spec"], st[K]["verify_spec"]
    assert b.startswith("项目目标：让布艺店主十分钟上架一款新品\n\n架构规范（预设 python-fastapi")
    assert b.index("架构规范（预设") < b.index("施工岗")
    head = b.split("施工岗")[0]
    assert "源码根 api/" in head and "按类型平铺" in head and "不新开目录" in head and "→" in head and "madr" in head and "{KIT}" not in head
    assert "迁移：migrations/" in head and "httpx" in head
    assert "架构规范检查（预设 python-fastapi" in v and "evo -p AB arch check" in v and "pip install import-linter" in v and v.index("架构规范检查") < v.index("验收岗")
    assert "架构规范" not in st["AB-UX-001"]["build_spec"] and "UI 规范（预设 web-react" in st["AB-UX-001"]["build_spec"]
    assert "架构规范（预设" in st["AB-FEAT-001"]["build_spec"]


# ---------- 4 交卷时的结构检查 ----------
def test_new_dir_in_by_type_layout_rejected_before_verify(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    commit(loop, repo, TB_LIKE)
    loop.plan(build=["file:api/services/pricing.py"])
    loop.add("AB", "加定价服务", "api/")
    loop.run_until("AB", lambda s: s["items"][K]["round"] >= 1)
    rw = [e for e in events(loop) if e["event"] == "rework"]
    assert rw and "api/services/" in rw[0]["why"] and "按类型平铺" in rw[0]["why"] and "arch_overrides" in rw[0]["why"]
    assert not [w for w in loop.workers() if w["role"] == "verify"]


def test_existing_dir_ok_and_allow_dirs_override(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    commit(loop, repo, TB_LIKE)
    loop.plan(build=["file:api/routers/prices.py"])
    loop.add("AB", "加价格接口", "api/")
    loop.run_until("AB", state_is("merged"))
    assert loop.item("AB")["round"] == 0
    loop.patch_cfg("AB", arch_overrides={"allow_dirs": ["api/services"]})              # 老板批准后
    loop.plan(build=["file:api/services/pricing.py"])
    loop.add("AB", "加定价服务", "api/")
    loop.run_until("AB", state_is("merged", "AB-FIX-002"))
    assert loop.item("AB", "AB-FIX-002")["round"] == 0


def test_domain_layout_new_domain_package_ok(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    commit(loop, repo, {"src/__init__.py": "", "src/main.py": "", "src/auth/__init__.py": "", "src/auth/router.py": ""})
    loop.plan(build=["file:src/orders/router.py"])
    loop.add("AB", "加订单领域", "src/")
    loop.run_until("AB", state_is("merged"))
    assert loop.item("AB")["round"] == 0


def test_node_banned_dep_rejected(loop):
    repo = loop.project("AB", arch_preset="node-ts")
    commit(loop, repo, {"src/apps/orders/domain/service.ts": "export {}\n", "package.json": json.dumps({"name": "x", "dependencies": {"fastify": "^5"}})})
    loop.plan(build=["dep:axios"])
    loop.add("AB", "接第三方接口", "src/")
    loop.run_until("AB", lambda s: s["items"][K]["round"] >= 1)
    why = [e for e in events(loop) if e["event"] == "rework"][0]["why"]
    assert "axios" in why and "HTTP 客户端" in why


def test_node_unexplained_dep_is_advisory(loop):
    repo = loop.project("AB", arch_preset="node-ts")
    commit(loop, repo, {"src/apps/orders/domain/service.ts": "export {}\n"})
    loop.plan(build=["dep:left-pad"])
    loop.add("AB", "补一个工具", "src/")
    loop.run_until("AB", state_is("merged"))
    adv = [e for e in events(loop) if e["event"] == "arch_advisory"]
    assert adv and "left-pad" in adv[0]["notes"][0] and loop.item("AB")["round"] == 0


def test_no_preset_no_structure_check(loop):
    repo = loop.project("AB")
    commit(loop, repo, TB_LIKE)
    loop.plan(build=["file:api/services/pricing.py"])
    loop.add("AB", "加定价服务", "api/")
    loop.run_until("AB", state_is("merged"))
    assert loop.item("AB")["round"] == 0 and not [e for e in events(loop) if e["event"] == "arch_advisory"]


# ---------- 5 arch check（只看新增） ----------
def test_arch_check_cli_python_layers_migrations_secrets_dirs(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    base = commit(loop, repo, {**TB_LIKE, "api/schemas.py": "from api import items_repo\n"})   # 老代码里已有一处向上依赖：不管
    commit(loop, repo, {
        "api/db.py": "from api import config\nfrom api.routers import items\nfrom api import (\n    search_service,\n)\n",
        "api/items_repo.py": "from api import db\nfrom fastapi import HTTPException\nimport os\nX = os.getenv('X')\nAPI_KEY = 'sk9f8a7b6c5d4e3'\ntoken_type = 'access_token'\n",
        "api/routers/items.py": "from fastapi import APIRouter\nfrom api import items_repo\nfrom api import search_service\n",   # 向下：合规
        "migrations/002_dup.sql": "--\n", "migrations/3_bad.sql": "--\n", "migrations/003_prices.sql": "--\n",
        "api/tests/sub/test_x.py": "PASSWORD = 'hunter2abc123'\n",                         # 测试目录：新目录和口令都不管
        "newtop/a.txt": "x\n", "docs/decisions/0001-x.md": "# x\n", "requirements.txt": TB_LIKE["requirements.txt"] + "requests\nflake8\n",
    }, "feat")
    r = loop.evo("-p", "AB", "arch", "check", "--path", repo, "--base", base, "--json", "--no-tools")
    assert r.returncode == 1, r.stdout + r.stderr
    j = json.loads(r.stdout)
    txt = "\n".join(v["text"] for v in j["violations"])
    kinds = {v["kind"] for v in j["violations"]}
    assert kinds == {"dir", "migration", "layer", "secret", "deps"}
    assert "api/db.py:2" in txt and "api/routers/items.py" in txt.split("api/db.py:2")[1].split("\n")[0]
    assert "api/db.py:4" in txt and "search_service" in txt                             # 跨行 from x import ( … )
    assert "items_repo.py:2" in txt and "fastapi" in txt
    assert "items_repo.py:5" in txt and "items_repo.py:6" not in txt                     # access_token 不是密钥
    assert "002_dup.sql" in txt and "3_bad.sql" in txt and "003_prices" not in txt
    assert "newtop/" in txt and "api/tests" not in txt and "docs/decisions" not in txt
    assert "requests" in txt and "flake8" in txt
    assert "schemas.py" not in txt                                                       # 老代码不追究
    assert "routers/items.py:" not in txt                                                # router → service/repo 是正方向
    assert any("config 模块外" in a for a in j["advisories"])
    r = loop.evo("-p", "AB", "arch", "check", "--path", repo, "--base", base, "--no-tools")
    assert r.returncode == 1 and "✗ 不合规" in r.stdout and "沿用现有" in r.stdout


def test_arch_check_clean_change_passes(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    base = commit(loop, repo, TB_LIKE)
    commit(loop, repo, {"api/routers/prices.py": "from fastapi import APIRouter\nfrom api import items_repo\n", "migrations/003_prices.sql": "--\n"})
    r = loop.evo("-p", "AB", "arch", "check", "--path", repo, "--base", base, "--no-tools")
    assert r.returncode == 0 and "✓ 没有问题" in r.stdout


def test_swift_layers_and_st_profile(loop):
    repo = loop.project("AB", arch_preset="swift-app", arch_overrides={"root": "App/Sources/App"})
    base = commit(loop, repo, {"App/Sources/App/Views/Home.swift": "import SwiftUI\n", "App/Sources/App/Engine/Score.swift": "import Foundation\n",
                               "App/Sources/App/Models/Stock.swift": "import Foundation\n"})
    commit(loop, repo, {"App/Sources/App/Engine/Score.swift": "import Foundation\nimport SwiftUI\n",
                        "App/Sources/App/Views/Home.swift": "import SwiftUI\nimport Charts\n",
                        "App/Sources/App/Package.swift": 'let p = Package(dependencies: [.package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.0.0")])\n'})
    j = json.loads(loop.evo("-p", "AB", "arch", "check", "--path", repo, "--base", base, "--json", "--no-tools").stdout)
    txt = "\n".join(v["text"] for v in j["violations"])
    assert "Engine/Score.swift:2" in txt and "SwiftUI" in txt and "Views/Home.swift" not in txt and "Alamofire" in txt
    st = json.load(open(os.path.join(KIT, "profiles", "st", "project.json"), encoding="utf-8"))
    tb = json.load(open(os.path.join(KIT, "profiles", "tubu", "project.json"), encoding="utf-8"))
    assert st["arch_preset"] == "swift-app" and st["arch_overrides"]["root"] == "REASTOCK/Sources/REASTOCK"
    assert tb["arch_preset"] == "python-fastapi" and tb["arch_overrides"]["root"] == "api" and tb["arch_overrides"]["layout"] == "by-type"
    eff = A.effective(st, files=[])
    assert A.touches_backend({"scope": ["REASTOCK/Sources/REASTOCK/Engine/"]}, eff)
    assert not A.touches_backend({"scope": ["docs/"]}, eff)


# ---------- 6 现有结构优先，只报一次 ----------
def test_existing_structure_wins_and_reported_once(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    commit(loop, repo, {**TB_LIKE, "requirements.txt": TB_LIKE["requirements.txt"] + "requests\n"})
    out = loop.ok("-p", "AB", "arch").stdout
    assert "仓库用的是 api/" in out and "按类型分（routers/）" in out and "^\\d{3}_" in out and "requests" in out
    for _ in range(3):
        loop.tick("AB")
    logs = [l for l in loop.state("AB")["log"] if "沿用现有、不迁移" in l]
    assert len(logs) == 1 and "api/" in logs[0]
    assert len([e for e in loop.outbox() if e["kind"] == "arch_conflict"]) == 1
    eff = A.effective({"arch_preset": "python-fastapi"}, files=list(TB_LIKE), present={"fastapi", "requests"})
    assert eff["categories"]["http"]["kept"] and "httpx*" in eff["categories"]["http"]["banned"]   # 现有的赢：再加 httpx 算重复


def test_show_preview_does_not_change_config(loop):
    repo = loop.project("AB")
    commit(loop, repo, TB_LIKE)
    out = loop.ok("-p", "AB", "arch", "show", "python-fastapi").stdout
    assert "沿用现有" in out and "arch_preset" not in json.load(open(loop.cfg_path("AB")))


# ---------- 7 小部件 ----------
def test_migration_pattern_inference_and_layer_of():
    assert A._infer_mig_pattern(["001_init.sql", "004_x.sqlite.sql"]) == r"^\d{3}_[a-z0-9_]+(\.sql|\.sqlite\.sql)$"
    assert A._infer_mig_pattern(["init.sql", "002_x.sql"]) is None
    eff = A.effective({"arch_preset": "python-fastapi"}, files=list(TB_LIKE), present=set())
    names = [l["name"] for l in eff["layers"]]
    lay = lambda p: (names[A.layer_of(p, eff)] if A.layer_of(p, eff) is not None else None)   # noqa: E731
    assert lay("routers/items.py") == "api" and lay("items_repo.py") == "repository" and lay("db.py") == "core"
    assert lay("search_service.py") == "service" and lay("main.py") == "entry" and lay("normalize.py") is None
    eff2 = A.effective({"arch_preset": "python-fastapi", "arch_overrides": {"layers.service": ["auth.py", "batch_*.py"]}}, files=list(TB_LIKE), present=set())
    assert A.layer_of("auth.py", eff2) == names.index("service") and A.layer_of("batch_import.py", eff2) == names.index("service")


def test_generated_contracts():
    files = list(TB_LIKE)
    eff = A.effective({"arch_preset": "python-fastapi"}, files=files, present=set())
    ini = A.importlinter_contract(eff, files)
    assert "root_package = api" in ini and "type = layers" in ini and "api.main" in ini and "api.routers.items" in ini
    assert ini.index("api.routers.items") < ini.index("api.search_service") < ini.index("api.items_repo") < ini.index("api.config")
    assert "__init__" not in ini and "api.tests" not in ini
    node = A.effective({"arch_preset": "node-ts"}, files=["src/apps/a/domain/x.ts"], present=set())
    rules = A.depcruise_rules(node)["forbidden"]
    assert any(r["name"] == "data-not-to-domain" for r in rules) and all(r["severity"] == "error" for r in rules)


def test_missing_tool_only_warns(tmp_path):
    eff = A.effective({"arch_preset": "python-fastapi"}, files=list(TB_LIKE), present=set())
    eff["checks"] = [{"id": "ruff", "label": "ruff", "tool": "evo-no-such-tool-xyz", "install": "pip install ruff", "what": ""}]
    r = A.run_tools(str(tmp_path), "HEAD", "HEAD", eff, ["api/x.py"])
    assert r[0]["status"] == "missing" and "pip install ruff" in r[0]["notes"][0]


@pytest.mark.skipif(not shutil.which("lint-imports"), reason="本机没装 import-linter")
def test_import_linter_counts_only_new_breaks(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    base = commit(loop, repo, {**TB_LIKE, "api/schemas.py": "from api import items_repo\n"})       # 老违约
    commit(loop, repo, {"api/db.py": "from api import config\nfrom api import search_service\n"}, "bad")
    eff = A.effective_at({"arch_preset": "python-fastapi"}, repo, base)
    res = {t["id"]: t for t in A.run_tools(repo, base, "HEAD", eff, ["api/db.py"])}
    il = res["import-linter"]
    assert il["status"] == "fail" and any("api.db" in n for n in il["notes"]) and not any("api.schemas" in n for n in il["notes"])


@pytest.mark.skipif(not shutil.which("ruff"), reason="本机没装 ruff")
def test_ruff_counts_only_added_lines(loop):
    repo = loop.project("AB", arch_preset="python-fastapi")
    base = commit(loop, repo, {**TB_LIKE, "api/normalize.py": "import os\nimport sys\n"})          # 老文件里已有 F401
    commit(loop, repo, {"api/normalize.py": "import os\nimport sys\nimport json\n", "api/routers/x.py": "import re\n"}, "new")
    eff = A.effective_at({"arch_preset": "python-fastapi"}, repo, base)
    res = {t["id"]: t for t in A.run_tools(repo, base, "HEAD", eff, ["api/normalize.py", "api/routers/x.py"])}
    notes = "\n".join(res["ruff"]["notes"])
    assert res["ruff"]["status"] == "fail" and "api/normalize.py:3" in notes and "api/routers/x.py:1" in notes
    assert "api/normalize.py:1 " not in notes and "api/normalize.py:2 " not in notes
