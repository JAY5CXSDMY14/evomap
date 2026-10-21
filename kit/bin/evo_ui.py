"""UI 栈预设（第十三轮）：kit/presets/ui/<名>.json → 本项目实际生效的规范、任务书里的「UI 规范」块、依赖检查。

老板的四条原则：优先复用成熟库、组件源代码可控、统一设计语言、严格限制重复依赖。
- 项目配置 ui_preset：web-react | swiftui | none（默认 none = 不加任何东西）；ui_overrides：{类别: 包名 | [包名] | {choice, packages}}，老板批准换库。
- 旧项目：预设只管新代码。某一类仓库里已经在用禁用库 → 那一类沿用现有的（现有的赢），报一次，不迁移。
- 依赖检查只拦「新加」：对比 base 和 HEAD 的清单（package.json / Package.swift / Xcode 包引用）。
  lockfile（package-lock / pnpm-lock / yarn.lock / Package.resolved）里新出现的禁用库只提示：可能是传递依赖。
"""
import json, os, re, subprocess

KIT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PRESET_DIR = os.path.join(KIT, "presets", "ui")
NAMES = ("web-react", "swiftui", "none")
SKIP_DIRS = {"node_modules", ".git", ".build", "build", "dist", ".next", "DerivedData", "Pods", ".swiftpm", "vendor", "coverage"}
LOCKS = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Package.resolved")


def load_preset(name):
    if not name or name == "none":
        return None
    if name not in NAMES:
        raise ValueError(f"UI 预设只能是：{' | '.join(NAMES)}")
    return json.load(open(os.path.join(PRESET_DIR, name + ".json"), encoding="utf-8"))


def match(pkg, pat):
    p, q = pkg.lower(), pat.lower()
    return p.startswith(q[:-1]) if q.endswith("*") else p == q


def any_match(pkg, pats):
    return any(match(pkg, x) for x in pats)


# ---------- 读依赖清单 ----------
def deps_from(path, text):
    """一个文件里的直接依赖名（清单）或锁定的名字（lockfile）。返回 (kind, set)。kind: manifest | lock | None"""
    base = os.path.basename(path)
    out = set()
    try:
        if base == "package.json":
            j = json.loads(text)
            for k in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                out |= set((j.get(k) or {}).keys())
            return "manifest", out
        if base == "Package.swift":
            for u in re.findall(r'\.package\s*\([^)]*?url:\s*"([^"]+)"', text, re.S):
                out.add(_repo_name(u))
            return "manifest", out
        if base == "project.pbxproj":
            for u in re.findall(r'repositoryURL\s*=\s*"([^"]+)"', text):
                out.add(_repo_name(u))
            return "manifest", out
        if base == "package-lock.json":
            j = json.loads(text)
            for k in (j.get("packages") or {}):
                if k.startswith("node_modules/") and "/node_modules/" not in k:
                    out.add(k[len("node_modules/"):])
            out |= set((j.get("dependencies") or {}).keys())
            return "lock", out
        if base == "pnpm-lock.yaml":
            for m in re.finditer(r"^\s{2,6}'?/?(@?[a-z0-9][\w.\-]*(?:/[\w.\-]+)?)'?(?:@[^:\s]*)?:\s*$", text, re.M):
                out.add(m.group(1))
            return "lock", out
        if base == "yarn.lock":
            for m in re.finditer(r'^"?(@?[^@\s"]+)@', text, re.M):
                out.add(m.group(1))
            return "lock", out
        if base == "Package.resolved":
            for u in re.findall(r'"(?:location|repositoryURL)"\s*:\s*"([^"]+)"', text):
                out.add(_repo_name(u))
            return "lock", out
    except ValueError:
        return None, out
    return None, out


def _repo_name(url):
    return re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1])


def _wanted(path):
    b = os.path.basename(path)
    return b in ("package.json", "Package.swift", "project.pbxproj") + LOCKS and not any(
        part in SKIP_DIRS for part in path.split("/")[:-1])


def repo_deps(repo):
    """工作目录里现有的直接依赖（只看清单，不看 lockfile）。"""
    found = set()
    if not repo or not os.path.isdir(repo):
        return found
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (d.startswith(".") and d != ".")]
        if root[len(repo):].count(os.sep) > 5:
            dirs[:] = []
        for f in files:
            if f in ("package.json", "Package.swift", "project.pbxproj"):
                try:
                    kind, s = deps_from(f, open(os.path.join(root, f), encoding="utf-8", errors="replace").read())
                except OSError:
                    continue
                if kind == "manifest":
                    found |= s
    return found


def _git(cwd, *a):
    r = subprocess.run(["git", "-C", cwd] + list(a), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def git_deps(repo, ref):
    """某个提交里的依赖：{manifest: set, lock: set}。"""
    out = {"manifest": set(), "lock": set()}
    ls = _git(repo, "ls-tree", "-r", "--name-only", ref) or ""
    for p in ls.splitlines():
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
def _override(v):
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",") if x.strip()]
    if isinstance(v, list):
        return {"choice": "、".join(v), "packages": v}
    if isinstance(v, dict):
        pk = v.get("packages") or []
        return {"choice": v.get("choice") or "、".join(pk), "packages": pk}
    return None


def effective(cfg, repo=None, present=None):
    """返回 None（没开预设）或 {name, title, principles, rules, ui_paths, component_dir, components, aliases,
    categories: {类别: {label, source, choice, packages, core, banned, existing, override, kept}}, conflicts: [...]}。"""
    pre = load_preset((cfg or {}).get("ui_preset") or "none")
    if not pre:
        return None
    present = repo_deps(repo or (cfg or {}).get("repo")) if present is None else present
    ovs = (cfg or {}).get("ui_overrides") or {}
    cats, conflicts = {}, []
    for name, c in list(pre["categories"].items()) + [(k, None) for k in ovs if k not in pre["categories"]]:
        c = dict(c or {"label": name, "source": "override", "choice": "", "packages": [], "banned": []})
        core = list(c.get("core") or c.get("packages") or [])
        banned = list(c.get("banned") or [])
        c["override"] = False
        ov = _override(ovs.get(name)) if name in ovs else None
        if ov and ov["packages"]:
            # 老板批准换库：换上的不再禁，原来选的反倒算同类第二个
            banned = [b for b in banned if not any(match(p, b) for p in ov["packages"])] + \
                     [x for x in core if not any(match(p, x) for p in ov["packages"])]
            c.update(choice=ov["choice"] + "（老板批准，ui_overrides）", packages=ov["packages"], override=True)
            core = list(ov["packages"])
        found = sorted(p for p in present if any_match(p, banned))
        c["existing"], c["kept"] = found, False
        if found:
            has_core = any(any_match(p, core) for p in present)
            banned = [b for b in banned if not any(match(p, b) for p in found)]
            if not has_core:            # 现有的赢：这一类沿用仓库里的库，预设选的反倒算重复
                banned += core
                c["kept"] = True
                c["choice"] = "沿用仓库现有的 " + "、".join(found) + f"（预设是 {c['choice']}，旧栈优先，不迁移）"
                core = found
            conflicts.append({"category": name, "label": c.get("label", name), "existing": found, "kept": c["kept"]})
        c["core"], c["banned"] = core, banned
        cats[name] = c
    return {"name": pre["name"], "title": pre.get("title", pre["name"]), "principles": pre.get("principles") or [],
            "rules": pre.get("rules") or [], "ui_paths": (cfg or {}).get("ui_paths") or pre.get("ui_paths") or [],
            "component_dir": pre.get("component_dir") or "", "components": pre.get("components") or [],
            "aliases": pre.get("component_aliases") or {}, "categories": cats, "conflicts": conflicts}


def conflict_sig(eff):
    return json.dumps([[c["category"], c["existing"]] for c in (eff or {}).get("conflicts") or []], ensure_ascii=False)


def conflict_text(eff):
    out = []
    for c in eff["conflicts"]:
        if c["kept"]:
            out.append(f"{c['label']}：仓库已在用 {'、'.join(c['existing'])}，这一类沿用现有的（预设让位，不迁移）")
        else:
            out.append(f"{c['label']}：仓库里同时还有 {'、'.join(c['existing'])}（旧代码照旧，新代码用预设，不再新增）")
    return out


# ---------- 这件碰不碰界面 ----------
def touches_ui(it, eff):
    if not eff:
        return False
    if it.get("ui"):
        return True
    for s in it.get("scope") or []:
        s = s.strip()
        s = s[2:] if s.startswith("./") else s
        if s in ("", "*"):
            continue
        for p in eff["ui_paths"]:
            p = p.strip("/")
            if ("/" + s.rstrip("/") + "/").find("/" + p + "/") >= 0 or ("/" + p + "/").startswith("/" + s.rstrip("/") + "/"):
                return True
    return False


# ---------- 任务书里的块 ----------
def _short(banned, n=4):
    xs = [b.replace("/*", "") for b in banned]
    return "、".join(xs[:n]) + ("…" if len(xs) > n else "")


def _lines(eff):
    out = []
    for c in eff["categories"].values():
        tag = "" if c["source"] == "owner" or c["override"] or c["kept"] else "（建议）"
        line = f"- {c['label']}{tag}：{c['choice']}"
        if c["banned"]:
            line += f"｜不另加 {_short(c['banned'])}"
        out.append(line)
    return out


def builder_block(eff):
    lines = [f"UI 规范（预设 {eff['name']}；只管新写的代码，旧代码不迁移）：",
             "原则：" + "、".join(eff["principles"]) + "。"] + _lines(eff)
    lines.append("规矩：上面覆盖不了才加新依赖，并在交卷 changes 里写明为什么；新加禁用库或同类第二个库，接棒器直接打回。"
                 + ("界面组件先用 shadcn 已有的（npx shadcn@latest add <组件>），不手写同名组件。" if eff["components"] else
                    "先用系统组件和 SF Symbols；第三方 UI 库要老板批准（写进 ui_overrides）。"))
    return "\n".join(lines) + "\n\n"


def verifier_block(eff, code):
    lines = [f"UI 规范检查（预设 {eff['name']}）：",
             f"- 依赖检查：在工作区跑 `evo -p {code} ui check`（对比 package.json / lockfile / Package.swift）。"
             "新加了禁用库或同类第二个库 → 不通过；新依赖不在规范里、交卷又没写理由 → 不通过。",
             "- 手写组件（只提建议）：预设里已有的组件被另写一份（例如自己写 Button / Modal / Toast）→ 写进「建议另开 issue」，不单独作为不通过理由。"]
    lines += _lines(eff)
    return "\n".join(lines) + "\n\n"


def head(role, it, eff, code):
    if not eff or not touches_ui(it, eff):
        return ""
    return builder_block(eff) if role == "build" else verifier_block(eff, code) if role == "verify" else ""


# ---------- 依赖检查 ----------
def _cat_of(pkg, eff, key):
    for n, c in eff["categories"].items():
        if any_match(pkg, c[key]):
            return n, c
    return None, None


def _kebab(name):
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"-\1", name).lower()
    return s.replace("_", "-")


def handrolled(repo, base, head_ref, eff):
    """新加的界面文件，名字和预设已有组件撞了，又不在组件目录里 → 提示（不拦）。"""
    if not eff["components"]:
        return []
    names = set(eff["components"]); al = eff["aliases"]; cdir = eff["component_dir"].strip("/")
    out = []
    diff = _git(repo, "diff", "--name-only", "--diff-filter=A", base, head_ref) or ""
    for p in diff.splitlines():
        m = re.search(r"([^/]+)\.(tsx|jsx|vue|svelte)$", p)
        if not m or (cdir and ("/" + cdir + "/") in ("/" + p)):
            continue
        k = _kebab(m.group(1))
        k = {"index": _kebab(p.split("/")[-2]) if "/" in p else "index"}.get(k, k)
        hit = k if k in names else al.get(k)
        if hit:
            out.append({"path": p, "component": hit})
    return out


def check(repo, base, head_ref, eff):
    """返回 {violations, lock_only, new_deps, handrolled}。violations 非空 = 不合规。"""
    b, h = git_deps(repo, base), git_deps(repo, head_ref)
    added = sorted(h["manifest"] - b["manifest"])
    lock_added = sorted((h["lock"] - b["lock"]) - h["manifest"])
    viol, new, lock_only = [], [], []
    for p in added:
        n, c = _cat_of(p, eff, "banned")
        if c:
            viol.append({"package": p, "category": n, "label": c["label"], "choice": c["choice"]})
        elif not _cat_of(p, eff, "packages")[0]:
            new.append(p)
    for p in lock_added:
        n, c = _cat_of(p, eff, "banned")
        if c:
            lock_only.append({"package": p, "category": n, "label": c["label"]})
    return {"violations": viol, "lock_only": lock_only, "new_deps": new, "handrolled": handrolled(repo, base, head_ref, eff)}


def violation_text(v):
    return "；".join(f"{x['label']}已定「{x['choice']}」，又加了 {x['package']}" for x in v)


def table(eff):
    """evo ui show 用的表。"""
    rows = [f"UI 预设：{eff['name']}（{eff['title']}）", "原则：" + "、".join(eff["principles"]), ""]
    for n, c in eff["categories"].items():
        src = {"owner": "老板定", "suggested": "建议", "override": "老板批准"}.get(c["source"], c["source"])
        if c["override"]:
            src = "老板批准"
        rows.append(f"  {c['label']}（{n}，{src}）：{c['choice']}")
        if c["banned"]:
            rows.append(f"      不另加：{'、'.join(x for x in c['banned'])}")
    if eff["conflicts"]:
        rows += ["", "仓库现有栈（现有的赢，只报这一次也会写进日志）："] + ["  · " + t for t in conflict_text(eff)]
    return "\n".join(rows)
