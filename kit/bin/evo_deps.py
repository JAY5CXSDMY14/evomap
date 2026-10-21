"""evo 内核库：读依赖清单、按类别算「选定 / 禁用 / 现有的赢」（第十八轮从 evo_ui 抽出来）。

UI 预设（kit/features/ui-preset）和架构预设（kit/features/arch-preset）都用它；功能包之间不互相 import，共用的东西放内核库。
只用标准库。
"""
import json, os, re

SKIP_DIRS = {"node_modules", ".git", ".build", "build", "dist", ".next", "DerivedData", "Pods", ".swiftpm", "vendor", "coverage"}
LOCKS = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Package.resolved")


def match(pkg, pat):
    p, q = pkg.lower(), pat.lower()
    return p.startswith(q[:-1]) if q.endswith("*") else p == q


def any_match(pkg, pats):
    return any(match(pkg, x) for x in pats)


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


def _override(v):
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",") if x.strip()]
    if isinstance(v, list):
        return {"choice": "、".join(v), "packages": v}
    if isinstance(v, dict):
        pk = v.get("packages") or []
        return {"choice": v.get("choice") or "、".join(pk), "packages": pk}
    return None


def resolve_categories(categories, present, ovs, ov_key="ui_overrides"):
    """按类别算「选定 / 禁用 / 现有的赢」，返回 (cats, conflicts)。UI 预设和架构预设（evo_arch，第十五轮）共用。"""
    ovs = ovs or {}
    cats, conflicts = {}, []
    for name, c in list(categories.items()) + [(k, None) for k in ovs if k not in categories]:
        c = dict(c or {"label": name, "source": "override", "choice": "", "packages": [], "banned": []})
        core = list(c.get("core") or c.get("packages") or [])
        banned = list(c.get("banned") or [])
        c["override"] = False
        ov = _override(ovs.get(name)) if name in ovs else None
        if ov and ov["packages"]:
            # 老板批准换库：换上的不再禁，原来选的反倒算同类第二个
            banned = [b for b in banned if not any(match(p, b) for p in ov["packages"])] + \
                     [x for x in core if not any(match(p, x) for p in ov["packages"])]
            c.update(choice=ov["choice"] + f"（老板批准，{ov_key}）", packages=ov["packages"], override=True)
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
    return cats, conflicts


def _short(banned, n=4):
    xs = [b.replace("/*", "") for b in banned]
    return "、".join(xs[:n]) + ("…" if len(xs) > n else "")
