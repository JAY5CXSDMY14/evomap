"""后端 / 架构预设（第十五轮）：kit/presets/arch/<名>.json → 本项目实际生效的目录与分层规范、任务书里的「架构规范」块、交卷时的结构检查。

和 UI 预设（evo_ui.py）同一套口径：
- 项目配置 arch_preset：python-fastapi | node-ts | swift-app | none（默认 none = 什么都不加）；
  arch_overrides：root / layout / allow_dirs / migrations_dir / migrations_pattern / arch_paths / config_modules /
  layers.<层> / deps.<类别> / checks.<检查>=off，老板批准的改动写这里。
- 只管新写的代码：所有检查只看本件「新增」的目录、文件、行；老代码不整体迁移。
- 仓库已有自己的结构（源码根不同、按类型平铺、迁移目录不同、某类库已在用别的）→ 沿用现有，evo 只报一次。
- 打回只有三种：新开了约定外的目录 / 新加了向上（反方向）的依赖或在下层用了 Web 框架 / 新加禁用库、迁移命名或编号不对、写死口令。
  其余（新依赖没写理由、在 config 模块外读环境变量、新领域包里文件名不常规、ruff/SwiftLint 提示）只提示。
- 外部工具（import-linter、ruff、dependency-cruiser、SwiftLint）装了才跑，没装只警告并给安装命令；它们的结果同样只算新增。
"""
import fnmatch, json, os, re, shutil, subprocess, tempfile

import evo_deps as UI      # 第十八轮：共用的依赖工具在内核库（以前 import evo_ui）

try:
    import tomllib
except ImportError:          # Python < 3.11：pyproject 只用正则粗读
    tomllib = None

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))   # 第十八轮：搬到 kit/features/arch-preset/
PRESET_DIR = os.path.join(KIT, "presets", "arch")
NAMES = ("python-fastapi", "node-ts", "swift-app", "none")
EXT = {"python": (".py",), "ts": (".ts", ".tsx", ".mts", ".cts", ".js", ".mjs", ".cjs"), "swift": (".swift",)}
OV_KEYS = ("root", "layout", "allow_dirs", "migrations_dir", "migrations_pattern", "arch_paths", "config_modules")
SECRET_RE = re.compile(r"""(?i)\b(password|passwd|secret|api_?key|access_?key|private_?key|token)\w*\s*[:=]\s*["']([^"'\s<>{}$%]{8,})["']""")
DSN_RE = re.compile(r"""(?i)["'](postgres(ql)?|mysql|mongodb(\+srv)?|redis|amqp)://[^:"'\s/]+:[^@"'\s<>{}$]{3,}@""")


def load_preset(name):
    if not name or name == "none":
        return None
    if name not in NAMES:
        raise ValueError(f"架构预设只能是：{' | '.join(NAMES)}")
    return json.load(open(os.path.join(PRESET_DIR, name + ".json"), encoding="utf-8"))


def _git(cwd, *a):
    r = subprocess.run(["git", "-C", cwd] + list(a), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def files_at(repo, ref="HEAD"):
    out = _git(repo, "ls-tree", "-r", "--name-only", ref) if repo and os.path.isdir(repo) else None
    return [x for x in (out or "").splitlines() if x]


def dirs_of(files):
    ds = set()
    for f in files:
        parts = f.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            ds.add("/".join(parts[:i]))
    return ds


def _glob(path, pats):
    """分层归类、测试目录用：* 可以跨 /（任意深度）。"""
    return any(fnmatch.fnmatchcase(path, p) for p in pats)


def _seg_glob(path, pats):
    """目录约定用：* 只匹配一级目录名，不跨 /。"""
    for p in pats:
        rx = "^" + "/".join(re.escape(seg).replace(r"\*", "[^/]*") for seg in p.split("/")) + "$"
        if re.match(rx, path):
            return True
    return False


# ---------- 依赖清单：Python 自己读，package.json / Package.swift / Xcode / lockfile 复用 evo_ui ----------
PY_MANIFESTS = ("pyproject.toml", "setup.cfg", "Pipfile")
PY_LOCKS = ("poetry.lock", "uv.lock", "Pipfile.lock", "pdm.lock")


def _norm(name):
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _req_name(line):
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "git+", "http:", "https:", ".", "/")):
        return None
    m = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", line)
    return _norm(m.group(1)) if m else None


def _is_req(path):
    b = os.path.basename(path)
    return bool(re.fullmatch(r"requirements([-_.][\w.-]+)?\.(txt|in)", b)) or (
        b.endswith((".txt", ".in")) and "/requirements/" in "/" + path)


def deps_from(path, text):
    b = os.path.basename(path)
    out = set()
    if _is_req(path):
        for ln in text.splitlines():
            n = _req_name(ln)
            if n:
                out.add(n)
        return "manifest", out
    if b == "pyproject.toml":
        reqs = []
        if tomllib:
            try:
                j = tomllib.loads(text)
            except Exception:
                return None, out
            p = j.get("project") or {}
            reqs += p.get("dependencies") or []
            for v in (p.get("optional-dependencies") or {}).values():
                reqs += v
            for v in (j.get("dependency-groups") or {}).values():
                reqs += [x for x in v if isinstance(x, str)]
            po = (j.get("tool") or {}).get("poetry") or {}
            for sec in [po.get("dependencies") or {}, po.get("dev-dependencies") or {}] + \
                       [g.get("dependencies") or {} for g in (po.get("group") or {}).values()]:
                reqs += [k for k in sec if k.lower() != "python"]
        else:
            reqs = re.findall(r'^\s*"([A-Za-z0-9][^"]*)"\s*,?\s*$', text, re.M)
        for r in reqs:
            n = _req_name(r)
            if n:
                out.add(n)
        return "manifest", out
    if b in PY_LOCKS:
        for m in re.finditer(r'^name\s*=\s*"([^"]+)"', text, re.M):
            out.add(_norm(m.group(1)))
        return "lock", out
    return UI.deps_from(path, text)


def _wanted(path):
    b = os.path.basename(path)
    if any(part in UI.SKIP_DIRS or part in (".venv", "venv", "site-packages", "__pycache__") for part in path.split("/")[:-1]):
        return False
    return _is_req(path) or b in ("pyproject.toml",) + PY_LOCKS + ("package.json", "Package.swift", "project.pbxproj") + UI.LOCKS


def git_deps(repo, ref):
    out = {"manifest": set(), "lock": set()}
    for p in files_at(repo, ref):
        if not _wanted(p):
            continue
        txt = _git(repo, "show", f"{ref}:{p}")
        if txt is None:
            continue
        kind, s = deps_from(p, txt)
        if kind:
            out[kind] |= s
    return out


# ---------- 本项目实际生效的规范 ----------
def _list(v):
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x) for x in (v or [])]


def _detect_root(pre, dirs):
    for c in pre.get("root_candidates") or []:
        if "*" in c:
            hit = sorted(d for d in dirs if fnmatch.fnmatchcase(d, c) and d.count("/") == c.count("/"))
            if hit:
                return hit[0]
        elif c in dirs:
            return c
    return None


def _infer_mig_pattern(names):
    """从现有迁移文件名猜命名规则：都以 N 位数字 + _ 开头 → ^\\d{N}_…；猜不出 → None。"""
    names = [n for n in names if not n.startswith((".", "__")) and n not in ("README.md", "env.py", "script.py.mako")]
    if not names:
        return None
    m = [re.match(r"^(\d+)_", n) for n in names]
    if all(m) and len({len(x.group(1)) for x in m}) == 1:
        exts = sorted({re.sub(r"^[^.]*", "", n) for n in names})
        ext = "(" + "|".join(re.escape(e) for e in exts) + ")" if exts else ""
        return r"^\d{%d}_[a-z0-9_]+%s$" % (len(m[0].group(1)), ext)
    return None


def effective(cfg, repo=None, files=None, present=None):
    """返回 None（没开）或 {name, title, lang, principles, rules, root, layout, layouts, layers, folders, repo_dirs, test_dirs,
    config_modules, env_reads, migrations, adr_dir, arch_paths, categories, checks, conflicts: [{kind, sig, text}]}。"""
    cfg = cfg or {}
    pre = load_preset(cfg.get("arch_preset") or "none")
    if not pre:
        return None
    repo = repo or cfg.get("repo")
    files = files_at(repo) if files is None else files
    dirs = dirs_of(files)
    ov = cfg.get("arch_overrides") or {}
    conflicts = []

    # 源码根：overrides > 预设默认（存在时）> 现有候选 > 预设默认
    root = str(ov.get("root") or "").strip("/")
    if not root:
        root = pre["root"]
        if files and pre["root"] not in dirs:
            found = _detect_root(pre, dirs)
            if found:
                conflicts.append({"kind": "root", "sig": "root:" + found,
                                  "text": f"源码根：仓库用的是 {found}/（预设是 {pre['root']}/），沿用现有"})
                root = found
    # 布局：源码根下已有按类型分的目录（routers/ services/ Views/…）→ 沿用按类型平铺
    layout = ov.get("layout") or pre.get("layout") or "domain"
    if not ov.get("layout") and files:
        bt = sorted(d.split("/")[-1] for d in dirs if d.rsplit("/", 1)[0] == root and d.split("/")[-1] in pre.get("by_type_dirs", []))
        if bt:
            layout = "by-type"
            conflicts.append({"kind": "layout", "sig": "layout:" + ",".join(bt),
                              "text": f"目录布局：{root}/ 下已按类型分（{'、'.join(d + '/' for d in bt)}），沿用现有；不按领域重排，新代码放进对应的现有目录"})
    if layout not in pre["layouts"]:
        layout = pre.get("layout") or "domain"

    layers = [dict(l) for l in pre["layers"]]
    for l in layers:
        extra = _list(ov.get("layers." + l["name"]) or (ov.get("layers") or {}).get(l["name"]))
        if extra:
            l["match"] = extra + [m for m in l["match"] if m not in extra]
            l["override"] = True

    # 迁移
    mig = dict(pre.get("migrations") or {}) or None
    if mig is not None:
        md = str(ov.get("migrations_dir") or "").strip("/")
        if md:
            mig["dir"] = md
        elif files and mig["dir"] not in dirs:
            alt = next((d for d in mig.get("alt_dirs") or [] if d in dirs), None)
            if alt:
                mig["dir"] = alt
                names = [f.split("/")[-1] for f in files if f.rsplit("/", 1)[0] == alt]
                guess = _infer_mig_pattern(names)
                mig["pattern"] = guess
                mig["label"] = f"沿用现有 {alt}/" + (f"（按现有文件名：{guess}）" if guess else "（命名规则猜不出，不查）")
                conflicts.append({"kind": "migrations", "sig": "mig:" + alt + ":" + str(guess),
                                  "text": f"数据库迁移：仓库用 {alt}/（预设是 {pre['migrations']['dir']}/、{pre['migrations']['label']}），沿用现有"
                                          + (f"，新迁移照现有命名 {guess}" if guess else "")})
        if ov.get("migrations_pattern"):
            mig["pattern"] = ov["migrations_pattern"]
            mig["label"] = f"{mig['dir']}/：{ov['migrations_pattern']}（arch_overrides）"

    present = git_deps(repo, "HEAD")["manifest"] if present is None and repo and files else (present or set())
    deps_ov = {k[5:]: v for k, v in ov.items() if k.startswith("deps.")}
    deps_ov.update(ov.get("deps") or {})
    cats, dep_conf = UI.resolve_categories(pre.get("categories") or {}, present, deps_ov, "arch_overrides")
    for c in dep_conf:
        conflicts.append({"kind": "deps", "sig": f"deps:{c['category']}:{','.join(c['existing'])}",
                          "text": (f"{c['label']}：仓库已在用 {'、'.join(c['existing'])}，这一类沿用现有的（预设让位，不迁移）" if c["kept"] else
                                   f"{c['label']}：仓库里同时还有 {'、'.join(c['existing'])}（旧代码照旧，新代码用预设，不再新增）")})
    off = {k[7:] for k, v in ov.items() if k.startswith("checks.") and str(v).lower() in ("off", "false", "0", "no")}
    checks = [c for c in pre.get("checks") or [] if c["id"] not in off]
    paths = _list(ov.get("arch_paths")) or ([root + "/"] + ([mig["dir"] + "/"] if mig else []))
    return {"name": pre["name"], "title": pre.get("title", pre["name"]), "lang": pre["lang"],
            "principles": pre.get("principles") or [], "rules": pre.get("rules") or [], "sources": pre.get("sources") or [],
            "root": root, "layout": layout, "layout_label": pre["layouts"][layout]["label"], "layouts": pre["layouts"],
            "layers": layers, "folders": pre.get("folders") or [], "repo_dirs": pre.get("repo_dirs") or [],
            "test_dirs": pre.get("test_dirs") or [], "allow_dirs": [d.strip("/") for d in _list(ov.get("allow_dirs"))],
            "config_modules": _list(ov.get("config_modules")) or pre.get("config_modules") or [], "env_reads": pre.get("env_reads") or [],
            "migrations": mig, "adr_dir": pre.get("adr_dir") or "docs/decisions", "arch_paths": paths,
            "categories": cats, "checks": checks, "ruff_select": pre.get("ruff_select") or "",
            "conflicts": conflicts, "overrides": ov}


def effective_at(cfg, repo, ref):
    """按某个提交（通常是改动前的 base）算「现有」：目录、迁移、依赖都按那一刻，本件新加的不算现有。"""
    return effective(cfg, repo, files=files_at(repo, ref), present=git_deps(repo, ref)["manifest"])


def conflict_sig(eff):
    return json.dumps([c["sig"] for c in (eff or {}).get("conflicts") or []], ensure_ascii=False)


def conflict_text(eff):
    return [c["text"] for c in (eff or {}).get("conflicts") or []]


# ---------- 这件碰不碰后端 ----------
def touches_backend(it, eff):
    if not eff:
        return False
    for s in it.get("scope") or []:
        s = s.strip()
        s = s[2:] if s.startswith("./") else s
        if s in ("", "*"):
            continue
        for p in eff["arch_paths"]:
            p = p.strip("/")
            a, b = "/" + s.rstrip("/") + "/", "/" + p + "/"
            if a.startswith(b) or b.startswith(a):
                return True
    return False


# ---------- 任务书里的块 ----------
def _layer_line(eff):
    return " → ".join(l["label"].split("（")[0] for l in eff["layers"])


def _dep_lines(eff):
    out = []
    for c in eff["categories"].values():
        tag = "（老板批准）" if c["override"] else ""
        line = f"- {c['label']}{tag}：{c['choice']}"
        if c["banned"]:
            line += f"｜不另加 {UI._short(c['banned'])}"
        out.append(line)
    return out


def _where(eff):
    r = eff["root"]
    if eff["layout"] == "by-type":
        return f"目录：源码根 {r}/，{eff['layout_label']}——新文件放进现有对应目录，照现有文件的命名，不新开目录。"
    return f"目录：源码根 {r}/，{eff['layout_label']}——新领域在 {r}/ 下建一个包，包内文件名照规范。"


def builder_block(eff):
    lines = [f"架构规范（预设 {eff['name']}；只管新写的代码，老代码不迁移）：",
             "原则：" + "、".join(eff["principles"]) + "。",
             _where(eff),
             "分层（只许从左往右依赖）：" + _layer_line(eff) + "。"]
    if eff["migrations"]:
        lines.append(f"迁移：{eff['migrations']['dir']}/，{eff['migrations']['label']}；只加新文件，不改已合并的。")
    lines += [r for r in eff["rules"] if r.startswith(("红线", "依赖方向", "配置走环境变量", "配置与密钥"))]
    lines += _dep_lines(eff)
    lines.append(f"规矩：上面覆盖不了才加新依赖，交卷 changes 里写明为什么；新开目录/新分层/换库先 ask 决策岗，批准后写进 arch_overrides，"
                 f"并在 {eff['adr_dir']}/ 补一份 ADR（模板 {{KIT}}/vendor/madr/template/adr-template-minimal.md）。全文见 {{KIT}}/presets/arch/README.md。")
    return "\n".join(lines).replace("{KIT}", KIT) + "\n\n"


def verifier_block(eff, code):
    lines = [f"架构规范检查（预设 {eff['name']}）：",
             f"- 结构检查：在工作区跑 `evo -p {code} arch check`（对比 merge-base..HEAD，只看本件新增）。有 ✗ → 不通过："
             "约定外的新目录、向上（反方向）的新依赖、下层用了 Web 框架/界面框架、新加禁用库或同类第二个库、迁移命名或编号不对、写死口令。"]
    for c in eff["checks"]:
        if c["id"] == "builtin":
            continue
        lines.append(f"- {c['label']}：arch check 会自动跑（{c['what']}）。本机没装就只警告——安装：{c['install']}；新出现的问题 → 不通过。")
    lines.append("- 只提示不拦：新依赖不在规范里又没写理由（按清单判不通过）、在 config 模块外直接读环境变量、新领域包文件名不常规，写进「建议另开 issue」。")
    lines += _dep_lines(eff)
    return "\n".join(lines).replace("{KIT}", KIT) + "\n\n"


def head(role, it, eff, code):
    if not eff or not touches_backend(it, eff):
        return ""
    return builder_block(eff) if role == "build" else verifier_block(eff, code) if role == "verify" else ""


# ---------- 分层：文件 → 层，import → 文件 ----------
def layer_of(rel, eff):
    """rel：相对源码根的路径。返回层下标（0 最上层）或 None（不在任何层，不查）。"""
    for i, l in enumerate(eff["layers"]):
        if _glob(rel, l["match"]):
            return i
    return None


def _rel_to_root(path, eff):
    r = eff["root"].strip("/")
    if not r:
        return path
    return path[len(r) + 1:] if path.startswith(r + "/") else None


def py_imports(line):
    """一行 Python 里 import 的模块（绝对名或 .相对名）。返回 [(模块, [名字])]。"""
    s = line.split("#", 1)[0].strip()
    m = re.match(r"from\s+(\.*[\w.]*)\s+import\s+\(?\s*(.*)", s)
    if m:
        names = [n.strip().split(" as ")[0].strip() for n in m.group(2).rstrip(")\\").split(",")]
        return [(m.group(1), [n for n in names if n and n != "("])]
    m = re.match(r"import\s+(.+)", s)
    if m:
        return [(x.strip().split(" as ")[0].strip(), []) for x in m.group(1).split(",") if x.strip()]
    return []


def _py_resolve(src, mod, names, fileset):
    """把 import 解析成仓库里的文件（可能多个：from pkg import a, b 里 a、b 是子模块）。"""
    if mod.startswith("."):
        dots = len(mod) - len(mod.lstrip("."))
        base = src.split("/")[:-1]
        base = base[:len(base) - (dots - 1)] if dots > 1 else base
        parts = base + [p for p in mod.lstrip(".").split(".") if p]
    else:
        parts = mod.split(".")
    out = []
    stem = "/".join(parts)
    cands = []
    for n in names or []:
        cands += [f"{stem}/{n}.py", f"{stem}/{n}/__init__.py"]
    hit = [c for c in cands if c in fileset]
    if hit:
        return hit
    for c in (stem + ".py", stem + "/__init__.py"):
        if c in fileset:
            out.append(c)
    return out


def ts_imports(line):
    return re.findall(r"""(?:from\s+|import\s*\(\s*|require\s*\(\s*|^\s*import\s+)["']([^"']+)["']""", line)


def _ts_resolve(src, spec, fileset):
    if not spec.startswith("."):
        return []
    base = os.path.normpath(os.path.join(os.path.dirname(src), spec)).replace(os.sep, "/")
    stem = re.sub(r"\.(js|mjs|cjs)$", "", base)
    for c in [base] + [stem + e for e in (".ts", ".tsx", ".mts", ".js", ".mjs")] + [stem + "/index" + e for e in (".ts", ".tsx", ".js")]:
        if c in fileset:
            return [c]
    return []


def _top(name):
    return name.split("/")[0] if not name.startswith("@") else "/".join(name.split("/")[:2])


def _forbidden(ext_name, pats):
    return [p for p in pats or [] if UI.match(ext_name, p) or UI.match(_top(ext_name), p) or UI.match(ext_name.split(".")[0], p)]


def added_lines(repo, base, head_ref, path):
    """本件在这个文件里新增的行：[(行号, 文本)]。"""
    d = _git(repo, "diff", "-U0", "--no-color", base, head_ref, "--", path) or ""
    out, n = [], 0
    for ln in d.splitlines():
        m = re.match(r"@@ -\S+ \+(\d+)(?:,\d+)? @@", ln)
        if m:
            n = int(m.group(1)); continue
        if ln.startswith("+") and not ln.startswith("+++"):
            out.append((n, ln[1:])); n += 1
    return out


def _is_test(path, eff):
    parts = path.split("/")
    b = parts[-1]
    return any(_glob("/".join(parts[:i]), eff["test_dirs"]) for i in range(1, len(parts))) or \
        b.startswith("test_") or b.endswith(("_test.py", ".test.ts", ".spec.ts", "Tests.swift", ".test.js", ".spec.js"))


# ---------- 检查（只看新增） ----------
def _dir_rule(d, eff, base_dirs):
    """一个新目录合不合约定：返回 None（合）或原因。"""
    if d in eff["allow_dirs"] or any(d.startswith(a + "/") for a in eff["allow_dirs"]) or _seg_glob(d, eff["allow_dirs"]):
        return None
    if _glob(d, eff["test_dirs"]) or any(_glob("/".join(d.split("/")[:i]), eff["test_dirs"]) for i in range(1, d.count("/") + 1)):
        return None
    if eff["adr_dir"] and (d == eff["adr_dir"] or eff["adr_dir"].startswith(d + "/")):
        return None
    if eff["migrations"] and (d == eff["migrations"]["dir"] or eff["migrations"]["dir"].startswith(d + "/")):
        return None
    root = eff["root"].strip("/")
    rel = d[len(root) + 1:] if root and d.startswith(root + "/") else (d if not root else None)
    if root and (d == root or root.startswith(d + "/")):
        return None
    if rel is None:                                   # 源码根外
        if "/" not in d and d not in eff["repo_dirs"] and not d.startswith("."):
            return f"仓库根新开了目录 {d}/（不在约定的顶层目录里）"
        return None
    if eff["layout"] == "by-type":
        return f"{root}/ 是按类型平铺的现有结构，新开了目录 {d}/"
    if _seg_glob(rel, eff["layouts"][eff["layout"]]["dirs"]):
        return None
    return f"新目录 {d}/ 不在「{eff['layout_label']}」的约定里"


def _secret(ln):
    if DSN_RE.search(ln):
        return True
    for m in SECRET_RE.finditer(ln):
        v = m.group(2)
        if re.search(r"\d", v) and re.search(r"[A-Za-z]", v) and not re.search(r"(?i)change.?me|example|placeholder|your[_-]|xxx|dummy|test", v):
            return True
    return False


def check(repo, base, head_ref, eff):
    """返回 {violations: [{kind, text}], advisories: [文本], new_deps: [包], lock_only: [...], changed: [文件]}。violations 非空 = 不合规。"""
    viol, adv = [], []
    base_files, head_files = set(files_at(repo, base)), files_at(repo, head_ref)
    fileset = set(head_files)
    base_dirs = dirs_of(base_files)
    added = [p for p in (_git(repo, "diff", "--name-only", "--diff-filter=A", base, head_ref) or "").splitlines() if p]
    changed = [p for p in (_git(repo, "diff", "--name-only", "--diff-filter=AM", base, head_ref) or "").splitlines() if p]

    # 1) 新目录
    new_dirs = sorted(dirs_of(added) - base_dirs, key=lambda d: (d.count("/"), d))
    flagged = []
    for d in new_dirs:
        if any(d.startswith(f + "/") for f in flagged):
            continue
        why = _dir_rule(d, eff, base_dirs)
        if why:
            flagged.append(d)
            viol.append({"kind": "dir", "text": why + "。先 ask 决策岗；批准后写进 arch_overrides.allow_dirs，并补一份 ADR"})
    # 新领域包里的文件名（按领域分包时）
    lay = eff["layouts"][eff["layout"]]
    if eff["layout"] == "domain" and lay.get("domain_files"):
        root = eff["root"].strip("/")
        for p in added:
            rel = _rel_to_root(p, eff)
            if rel and rel.count("/") == 1 and rel.split("/")[0] in {d[len(root) + 1:] for d in new_dirs if d.startswith(root + "/")} \
                    and p.endswith(".py") and rel.split("/")[1] not in lay["domain_files"]:
                adv.append(f"新领域包里的 {p} 不是常规文件名（{'、'.join(lay['domain_files'][1:6])}…）")

    # 2) 迁移
    mig = eff["migrations"]
    if mig:
        base_nums = {}
        for f in base_files:
            if f.rsplit("/", 1)[0] == mig["dir"]:
                m = re.match(r"^(\d+)_", f.split("/")[-1])
                if m:
                    base_nums.setdefault(m.group(1), f)
        for p in added:
            if p.rsplit("/", 1)[0] != mig["dir"]:
                continue
            name = p.split("/")[-1]
            if mig.get("pattern") and not re.match(mig["pattern"], name):
                viol.append({"kind": "migration", "text": f"新迁移 {name} 不符合命名约定 {mig['pattern']}（{mig['label']}）"})
            m = re.match(r"^(\d+)_", name)
            if m and m.group(1) in base_nums:
                viol.append({"kind": "migration", "text": f"新迁移 {name} 的编号 {m.group(1)} 和已有的 {base_nums[m.group(1)].split('/')[-1]} 撞了，往后顺延"})
        for p in changed:
            if p.rsplit("/", 1)[0] == mig["dir"] and p in base_files:
                adv.append(f"改了已有迁移 {p}（已合并的迁移应只增不改，确认它还没上线）")

    # 3) 新增的 import / 环境变量 / 口令
    exts = EXT[eff["lang"]]
    for p in changed:
        if not p.endswith(exts):
            continue
        rel = _rel_to_root(p, eff)
        test = _is_test(p, eff)
        src_layer = layer_of(rel, eff) if rel is not None and not test else None
        is_cfg = rel is not None and _glob(rel, eff["config_modules"]) or _glob(p, eff["config_modules"])
        pending = None                                 # from x import (  跨行的名字
        for n, ln in added_lines(repo, base, head_ref, p):
            if eff["lang"] == "python":
                if pending is not None:
                    body = ln.split("#", 1)[0]
                    names = [x.strip().split(" as ")[0].strip() for x in body.replace(")", "").split(",")]
                    ln_imports = [(pending, [x for x in names if re.fullmatch(r"\w+", x)])]
                    if ")" in body:
                        pending = None
                else:
                    ln_imports = py_imports(ln)
                    m = re.match(r"\s*from\s+(\.*[\w.]*)\s+import\s*\((?!.*\))", ln)
                    if m:
                        pending = m.group(1)
            if not test:
                if _secret(ln):
                    viol.append({"kind": "secret", "text": f"{p}:{n} 看起来把口令/密钥写死在代码里，改成从配置（环境变量）读"})
                if not is_cfg and any(e in ln for e in eff["env_reads"]):
                    adv.append(f"{p}:{n} 在 config 模块外直接读环境变量（应集中到 config，别处 import）")
            if src_layer is None:
                continue
            L = eff["layers"][src_layer]
            targets, externals = [], []
            if eff["lang"] == "python":
                for mod, names in ln_imports:
                    hit = _py_resolve(p, mod, names, fileset)
                    (targets.extend(hit) if hit else externals.append(mod.lstrip(".")) if not mod.startswith(".") else None)
            elif eff["lang"] == "ts":
                for spec in ts_imports(ln):
                    hit = _ts_resolve(p, spec, fileset)
                    (targets.extend(hit) if hit else externals.append(spec) if not spec.startswith(".") else None)
            else:
                m = re.match(r"\s*(?:@testable\s+)?import\s+(?:(?:struct|class|enum|protocol|func|var|typealias)\s+)?([\w]+)", ln)
                if m:
                    mod = m.group(1)
                    for j, l2 in enumerate(eff["layers"]):
                        if mod in (l2.get("modules") or []) and j < src_layer:
                            viol.append({"kind": "layer", "text": f"{p}:{n}（{L['label']}）新加了 import {mod}（{l2['label']}），方向反了：下层不许依赖上层"})
                    externals.append(mod)
            for t in targets:
                tr = _rel_to_root(t, eff)
                tl = layer_of(tr, eff) if tr is not None else None
                if tl is not None and tl < src_layer:
                    viol.append({"kind": "layer", "text": f"{p}:{n}（{L['label']}）新加了对 {t}（{eff['layers'][tl]['label']}）的依赖，方向反了：下层不许依赖上层"})
            for e in externals:
                bad = _forbidden(e, L.get("forbid_imports"))
                if bad:
                    viol.append({"kind": "layer", "text": f"{p}:{n}（{L['label']}）新加了 import {e}：这一层不许用 {'、'.join(bad)}"})

    # 4) 依赖
    b, h = git_deps(repo, base), git_deps(repo, head_ref)
    adds = sorted(h["manifest"] - b["manifest"])
    lock_added = sorted((h["lock"] - b["lock"]) - h["manifest"])
    new, lock_only = [], []
    for p in adds:
        hit = next(((n, c) for n, c in eff["categories"].items() if UI.any_match(p, c["banned"])), None)
        if hit:
            viol.append({"kind": "deps", "text": f"{hit[1]['label']}已定「{hit[1]['choice']}」，又加了 {p}。改用规范里的库；确实要换，先 ask 决策岗，老板批准后写进 arch_overrides"})
        elif not any(UI.any_match(p, c["packages"]) or UI.any_match(p, c["core"]) for c in eff["categories"].values()):
            new.append(p)
    for p in lock_added:
        hit = next(((n, c) for n, c in eff["categories"].items() if UI.any_match(p, c["banned"])), None)
        if hit:
            lock_only.append({"package": p, "label": hit[1]["label"]})
    adr = [p for p in added if eff["adr_dir"] and p.startswith(eff["adr_dir"] + "/")]
    if new and not adr:
        adv.append("新依赖 " + "、".join(new) + " 不在规范里：交卷 changes 写明为什么；影响架构的建议补一份 ADR")
    return {"violations": _dedup(viol), "advisories": list(dict.fromkeys(adv)), "new_deps": new, "lock_only": lock_only,
            "changed": changed, "added": added}


def _dedup(xs):
    seen, out = set(), []
    for x in xs:
        if x["text"] not in seen:
            seen.add(x["text"]); out.append(x)
    return out


def violation_text(v):
    return "；".join(x["text"] for x in v)


# ---------- 外部工具：装了才跑，只算新增 ----------
def _which(tool, repo):
    local = os.path.join(repo, "node_modules", ".bin", tool)
    return local if os.path.exists(local) else shutil.which(tool)


def _has_cfg(repo, kind):
    if kind == "import-linter":
        if os.path.exists(os.path.join(repo, ".importlinter")):
            return os.path.join(repo, ".importlinter")
        for f in ("setup.cfg", "pyproject.toml"):
            p = os.path.join(repo, f)
            if os.path.exists(p) and re.search(r"^\[(tool\.)?importlinter", open(p, encoding="utf-8", errors="replace").read(), re.M):
                return p
        return None
    if kind == "ruff":
        if any(os.path.exists(os.path.join(repo, f)) for f in ("ruff.toml", ".ruff.toml")):
            return True
        p = os.path.join(repo, "pyproject.toml")
        return os.path.exists(p) and "[tool.ruff" in open(p, encoding="utf-8", errors="replace").read()
    if kind == "dependency-cruiser":
        for f in (".dependency-cruiser.js", ".dependency-cruiser.cjs", ".dependency-cruiser.mjs", ".dependency-cruiser.json"):
            if os.path.exists(os.path.join(repo, f)):
                return os.path.join(repo, f)
    return None


def importlinter_contract(eff, files):
    """按本预设的分层，给仓库现有模块生成 import-linter 的 INI 契约（只列存在的模块；一层多个模块用 : 连，不要求互相独立）。"""
    root = eff["root"].strip("/")
    if not root or "/" in root:
        return None
    rows, fs = [], set(files)
    for l in eff["layers"]:
        mods = []
        for f in sorted(files):
            if not f.endswith(".py") or not f.startswith(root + "/"):
                continue
            rel = f[len(root) + 1:]
            if f.endswith("__init__.py") or _is_test(f, eff) or layer_of(rel, eff) != eff["layers"].index(l):
                continue
            parts = f.split("/")[:-1]          # 只收能 import 到的（每级目录都有 __init__.py）
            if any("/".join(parts[:i]) + "/__init__.py" not in fs for i in range(1, len(parts) + 1)):
                continue
            mods.append(f[:-3].replace("/", "."))
        if mods:
            rows.append(" : ".join(mods))
    if len(rows) < 2:
        return None
    return ("[importlinter]\nroot_package = " + root + "\n\n[importlinter:contract:evo-layers]\n"
            f"name = evo-{eff['name']}-layers\ntype = layers\nunmatched_ignore_imports_alerting = none\nlayers =\n"
            + "".join(f"    {r}\n" for r in rows))


def _broken(out):
    """import-linter / depcruise 的输出里每条违规（去掉行号，好比较改动前后）。"""
    keys = set()
    for ln in out.splitlines():
        s = ln.strip()
        if "->" in s or "→" in s:
            keys.add(re.sub(r"\s*\(l\.[\d, ]+\)|:\d+(:\d+)?", "", s))
    return keys


def _worktree(repo, ref):
    d = tempfile.mkdtemp(prefix="evo-arch-")
    r = subprocess.run(["git", "-C", repo, "worktree", "add", "-q", "--detach", d, ref], capture_output=True, text=True)
    return d if r.returncode == 0 else None


def _drop_worktree(repo, d):
    subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", d], capture_output=True)
    shutil.rmtree(d, ignore_errors=True)


def _run(cmd, cwd, timeout=300):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "PYTHONPATH": cwd + os.pathsep + os.environ.get("PYTHONPATH", "")})
        return r.returncode, r.stdout + r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 99, str(e)


def _before_after(repo, base, cmd_for):
    """在 HEAD 工作区和 base 的临时工作树各跑一次，返回 (新出现的违规, HEAD 输出)。cmd_for(目录) → 命令或 None。"""
    c = cmd_for(repo)
    if not c:
        return None, ""
    code, out = _run(c, repo)
    if code == 0:
        return set(), out
    now = _broken(out)
    if not now:                                        # 工具自己报错（配置、导入失败）：不算新违规，交给调用方当警告
        return "error", out
    wt = _worktree(repo, base)
    before = set()
    if wt:
        try:
            cb = cmd_for(wt)
            if cb:
                _, ob = _run(cb, wt)
                before = _broken(ob)
        finally:
            _drop_worktree(repo, wt)
    return now - before, out


def run_tools(repo, base, head_ref, eff, changed):
    """返回 [{id, label, status: pass|fail|missing|error|skip, notes: [..], install}]。fail 才算不通过；missing / error 只警告。"""
    res = []
    for c in eff["checks"]:
        if c["id"] == "builtin":
            continue
        r = {"id": c["id"], "label": c["label"], "install": c["install"], "notes": [], "status": "skip"}
        tool = _which(c["tool"], repo) if c["tool"] else None
        if c["tool"] and not tool:
            r["status"] = "missing"; r["notes"] = [f"没装 {c['tool']}，这项只警告。安装：{c['install']}"]
            res.append(r); continue
        if c["id"] == "import-linter":
            own = _has_cfg(repo, "import-linter")
            tmp = []

            def cmd_for(d, own=own):
                if own:
                    return [tool, "--no-cache", "--no-logo", "--config", os.path.join(d, os.path.relpath(own, repo))]
                txt = importlinter_contract(eff, files_at(d) if d != repo else files_at(repo, head_ref))
                if not txt:
                    return None
                f = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False, encoding="utf-8"); f.write(txt); f.close(); tmp.append(f.name)
                return [tool, "--no-cache", "--no-logo", "--config", f.name]
            new, out = _before_after(repo, base, cmd_for)
            for f in tmp:
                os.unlink(f)
            if new is None:
                r["notes"] = ["分层里能对上的模块不到两层，没生成契约（可在 arch_overrides 的 layers.<层> 里补模块路径）"]
            elif new == "error":
                r["status"] = "error"; r["notes"] = ["import-linter 自己报错（只警告）：" + out.strip()[-300:]]
            elif new:
                r["status"] = "fail"; r["notes"] = sorted(new)[:20]
            else:
                r["status"] = "pass"
        elif c["id"] == "ruff":
            py = [p for p in changed if p.endswith(".py") and os.path.exists(os.path.join(repo, p))]
            if not py:
                res.append(r); continue
            cmd = [tool, "check", "--output-format", "json", "--force-exclude"]
            if not _has_cfg(repo, "ruff") and eff["ruff_select"]:
                cmd += ["--select", eff["ruff_select"]]
            _, out = _run(cmd + py, repo)
            try:
                items = json.loads(out[out.index("["):]) if "[" in out else []
            except ValueError:
                items = []
            fresh = _only_added(repo, base, head_ref, [(os.path.relpath(i.get("filename", ""), repo), (i.get("location") or {}).get("row"),
                                                       f"{i.get('code')} {i.get('message')}") for i in items])
            r["status"] = "fail" if fresh else "pass"; r["notes"] = fresh[:20]
        elif c["id"] == "dependency-cruiser":
            own = _has_cfg(repo, "dependency-cruiser")
            tmp = []

            def cmd_for(d, own=own):
                cfgp = os.path.join(d, os.path.relpath(own, repo)) if own else None
                if not cfgp:
                    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
                    json.dump(depcruise_rules(eff), f); f.close(); tmp.append(f.name); cfgp = f.name
                return [tool if d == repo else (_which("depcruise", d) or tool), eff["root"], "--config", cfgp, "--output-type", "err"]
            new, out = _before_after(repo, base, cmd_for)
            for f in tmp:
                os.unlink(f)
            if new == "error":
                r["status"] = "error"; r["notes"] = ["dependency-cruiser 自己报错（只警告）：" + out.strip()[-300:]]
            else:
                r["status"] = "fail" if new else "pass"; r["notes"] = sorted(new or [])[:20]
        elif c["id"] == "swiftlint":
            sw = [p for p in changed if p.endswith(".swift") and os.path.exists(os.path.join(repo, p))]
            if not sw:
                res.append(r); continue
            _, out = _run([tool, "lint", "--quiet", "--reporter", "json"] + sw, repo)
            try:
                items = json.loads(out[out.index("["):]) if "[" in out else []
            except ValueError:
                items = []
            fresh = _only_added(repo, base, head_ref, [(os.path.relpath(i.get("file", ""), repo), i.get("line"),
                                                       f"{i.get('rule_id')} {i.get('reason')}") for i in items])
            r["status"] = "fail" if fresh else "pass"; r["notes"] = fresh[:20]
        res.append(r)
    return res


def _only_added(repo, base, head_ref, items):
    cache, out = {}, []
    for path, row, msg in items:
        if path not in cache:
            cache[path] = {n for n, _ in added_lines(repo, base, head_ref, path)}
        if row in cache[path]:
            out.append(f"{path}:{row} {msg}")
    return out


def depcruise_rules(eff):
    """按分层生成 dependency-cruiser 规则：下层不许依赖上层。"""
    root = re.escape(eff["root"].strip("/"))
    rules = []

    def rx(pats):
        return "|".join("^" + root + "/" + re.escape(p).replace(r"\*", ".*") + "$" for p in pats)
    for i, low in enumerate(eff["layers"]):
        for high in eff["layers"][:i]:
            rules.append({"name": f"{low['name']}-not-to-{high['name']}", "severity": "error",
                          "comment": f"{low['label']} 不许依赖 {high['label']}",
                          "from": {"path": rx(low["match"])}, "to": {"path": rx(high["match"])}})
    return {"forbidden": rules, "options": {"doNotFollow": {"path": "node_modules"}, "tsPreCompilationDeps": True}}


# ---------- evo arch show 用的表 ----------
def table(eff):
    rows = [f"架构预设：{eff['name']}（{eff['title']}）", "原则：" + "、".join(eff["principles"]), "",
            f"源码根：{eff['root']}/　布局：{eff['layout_label']}",
            "分层（只许从上往下依赖）："]
    for l in eff["layers"]:
        rows.append(f"  {l['label']}：{'、'.join(l['match'][:6])}{'…' if len(l['match']) > 6 else ''}"
                    + (f"｜不许用 {'、'.join(l['forbid_imports'])}" if l.get("forbid_imports") else "")
                    + ("（arch_overrides）" if l.get("override") else ""))
    if eff["migrations"]:
        rows.append(f"迁移：{eff['migrations']['dir']}/　{eff['migrations']['label']}")
    if eff["allow_dirs"]:
        rows.append("老板批准的新目录：" + "、".join(eff["allow_dirs"]))
    rows += ["", "依赖："]
    for n, c in eff["categories"].items():
        rows.append(f"  {c['label']}（{n}{'，老板批准' if c['override'] else ''}）：{c['choice']}")
        if c["banned"]:
            rows.append(f"      不另加：{'、'.join(c['banned'])}")
    rows += ["", "验收检查："] + [f"  · {c['label']}：{c['what']}" + (f"（安装：{c['install']}）" if c["install"] else "") for c in eff["checks"]]
    if eff["conflicts"]:
        rows += ["", "仓库现有结构（沿用现有，只报这一次也会写进日志）："] + ["  · " + t for t in conflict_text(eff)]
    return "\n".join(rows)
