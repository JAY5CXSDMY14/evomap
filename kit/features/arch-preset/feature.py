"""功能包 arch-preset：后端 / 架构预设（第十五轮的 evo_arch，第十八轮从内核搬出来）。

贡献：任务书开头的「架构规范」（prompt.head）、交卷结构检查（delivery.check）、每轮一次的冲突提示（tick.before_dispatch）、
status --json 的 arch_preset（status）、子命令 `evo arch`（cli）、服务 preset.arch（new/import 的 --arch-preset 用）。
"""
import json
import os
import re
import sys

import evo_arch as ARCH

K = None          # 内核接口（apply / in_use 时填上）


_ARCH = {}


def arch_eff():
    """本项目实际生效的架构规范（arch_preset=none 时 None）。一个进程算一次；预设文件坏了只提示、不拦接棒。"""
    if "eff" not in _ARCH:
        try:
            _ARCH["eff"] = ARCH.effective(K.CFG)
        except (ValueError, OSError, KeyError) as e:
            print(f"架构预设读不出：{e}", file=sys.stderr)
            _ARCH["eff"] = None
    return _ARCH["eff"]


def arch_conflicts_once(s):
    """仓库已有自己的结构（源码根、按类型平铺、迁移目录、某类库）：沿用现有，日志 + 提醒各一次；内容变了再报。"""
    eff = arch_eff()
    sig = ARCH.conflict_sig(eff) if eff and eff["conflicts"] else ""
    if sig and s.get("arch_reported") != sig:
        txt = "；".join(ARCH.conflict_text(eff))
        K.log(s, f"架构预设 {eff['name']} 与仓库现有结构不同，沿用现有、不迁移：{txt}")
        K.notify("arch_conflict", "架构预设：沿用仓库现有结构", txt)
    if sig or s.get("arch_reported"):
        s["arch_reported"] = sig


def arch_delivery_check(s, k, it):
    """施工交卷后、送验收前：只看本件新增的目录、文件、行（evo 内置检查，不跑外部工具）。
    约定外的新目录 / 向上依赖 / 下层用了 Web 框架 / 禁用库 / 迁移命名或编号 / 写死口令 → 打回原因；其余记提示（时间线 arch_advisory）。"""
    eff = arch_eff(); wt = it.get("worktree")
    if not eff or not wt:
        return None
    base = K.git(wt, "merge-base", K.CFG["main_branch"], "HEAD", check=False)
    if not base:
        return None
    eff = ARCH.effective_at(K.CFG, wt, base)          # 「现有」按改动前的主线算
    r = ARCH.check(wt, base, "HEAD", eff)
    rep = json.dumps(it.get("report") or {}, ensure_ascii=False)
    notes = [a for a in r["advisories"] if not (a.startswith("新依赖") and all(p in rep for p in r["new_deps"]))] + \
            [f"lockfile 新出现禁用库 {x['package']}（{x['label']}，可能是传递依赖）" for x in r["lock_only"]]
    if notes:
        it["arch_notes"] = notes
        K.tl(k, "arch_advisory", notes=notes)
        K.log(s, f"{k} 架构规范提示：" + "；".join(notes)[:200])
    if r["violations"]:
        return "不符合架构规范：" + ARCH.violation_text(r["violations"])[:900]
    return None


ARCH_SET_RE = re.compile(r"(root|layout|allow_dirs|migrations_dir|migrations_pattern|arch_paths|config_modules|layers\.[a-z][a-z0-9_-]{0,23}|deps\.[a-z][a-z0-9_-]{0,23}|checks\.[a-z][a-z0-9_-]{0,31})")


def cmd_arch(a):
    """evo -p AB arch [show [预设]]：看本项目生效的架构规范（带预设名 = 只预览）；arch set <预设> / set 键=值 / set 键=：改（外部 Agent 不能改）；
    arch check [--path 目录] [--base 提交] [--no-tools] [--json]：只看新增，有不合规退出码 1（验收岗用）。"""
    act = a.action or "show"
    if act == "show":
        pv = (a.text or [None])[0]
        if pv and pv not in ARCH.NAMES:
            sys.exit(f"架构预设只能是：{' | '.join(ARCH.NAMES)}")
        eff = ARCH.effective({**K.CFG, "arch_preset": pv}) if pv else arch_eff()
        if a.json:
            print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, "arch_preset": K.CFG.get("arch_preset") or "none", "effective": eff}, ensure_ascii=False, indent=1, default=list)); return
        print(ARCH.table(eff) if eff else "架构预设：none（没开；evo -p " + K.CODE + " arch set python-fastapi | node-ts | swift-app）"); return
    if act == "check":
        path = a.path or (os.getcwd() if K.git(os.getcwd(), "rev-parse", "--git-dir", check=False) else K.CFG["repo"])
        if not arch_eff():
            print("架构预设：none，不查"); return
        base = a.base or K.git(path, "merge-base", K.CFG["main_branch"], "HEAD", check=False) or "HEAD"
        eff = ARCH.effective_at(K.CFG, path, base)
        r = ARCH.check(path, base, "HEAD", eff)
        tools = [] if a.no_tools else ARCH.run_tools(path, base, "HEAD", eff, r["changed"])
        bad = bool(r["violations"]) or any(t["status"] == "fail" for t in tools)
        if a.json:
            print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, **r, "tools": tools, "ok": not bad}, ensure_ascii=False, indent=1))
        else:
            print(f"架构检查（预设 {eff['name']}，源码根 {eff['root']}/，对比 {base[:10]}..HEAD，只看新增）")
            for x in r["violations"]:
                print("  ✗ 不合规：" + x["text"])
            for x in r["lock_only"]:
                print(f"  ! 提示：lockfile 新出现禁用库 {x['package']}（{x['label']}，可能是传递依赖，核对一下）")
            for t in r["advisories"]:
                print("  ! 提示：" + t)
            for t in tools:
                mark = {"pass": "✓", "fail": "✗", "missing": "!", "error": "!", "skip": "·"}[t["status"]]
                head_ = {"pass": "通过", "fail": "不合规（新出现）", "missing": "没装，只警告", "error": "工具报错，只警告", "skip": "没有要查的文件"}[t["status"]]
                print(f"  {mark} {t['label']}：{head_}")
                for n in t["notes"][:12]:
                    print("      " + n)
            for t in ARCH.conflict_text(eff):
                print("  · 沿用现有：" + t)
            if not bad and not r["advisories"] and not r["lock_only"]:
                print("  ✓ 没有问题")
        sys.exit(1 if bad else 0)
    K.refuse_agents("改架构预设")
    arg = " ".join(a.text or []).strip()
    if not arg:
        sys.exit("用法：evo arch set python-fastapi | node-ts | swift-app | none，或 evo arch set 键=值（root、layout、allow_dirs、migrations_dir、"
                 "migrations_pattern、arch_paths、config_modules、layers.<层>、deps.<类别>、checks.<检查>=off；值留空 = 清掉）")
    c = K._read_json(K._project_cfg_path(K.CODE))
    if "=" in arg:
        key, _, val = arg.partition("=")
        key, val = key.strip(), val.strip()
        if not ARCH_SET_RE.fullmatch(key):
            sys.exit("键只能是 root、layout、allow_dirs、migrations_dir、migrations_pattern、arch_paths、config_modules、layers.<层>、deps.<类别>、checks.<检查>")
        if key == "layout" and val and val not in ("domain", "by-type"):
            sys.exit("layout 只能是 domain 或 by-type")
        if key == "migrations_pattern" and val:
            try:
                re.compile(val)
            except re.error as e:
                sys.exit(f"migrations_pattern 不是合法正则：{e}")
        elif val and not re.fullmatch(r"[@A-Za-z0-9._/*+, -]{1,200}", val):
            sys.exit("值只许字母数字和 @ . _ / * + - , 空格")
        ov = dict(c.get("arch_overrides") or {})
        if val:
            ov[key] = [x.strip() for x in val.split(",") if x.strip()] if key in ("allow_dirs", "arch_paths", "config_modules") or key.startswith(("layers.", "deps.")) else val
        else:
            ov.pop(key, None)
        if ov:
            c["arch_overrides"] = ov
        else:
            c.pop("arch_overrides", None)
        K._write_project_cfg(c)
        print(f"{K.CODE} 架构覆盖：{key} = {val or '（已清掉，回到预设）'}。下一份任务书起生效")
        return
    if arg not in ARCH.NAMES:
        sys.exit(f"架构预设只能是：{' | '.join(ARCH.NAMES)}")
    if arg == "none":
        c.pop("arch_preset", None)
    else:
        c["arch_preset"] = arg
    K._write_project_cfg(c)
    print(f"{K.CODE} 架构预设：{arg}。下一份任务书起生效（只管新代码，老结构沿用、不迁移）")
    eff = ARCH.effective({**K.CFG, **c}) if arg != "none" else None
    for t in ARCH.conflict_text(eff) if eff else []:
        print("  · 沿用现有：" + t)



def _head(role, it):
    return ARCH.head(role, it, arch_eff(), K.CODE)


def _status(s, doc):
    doc["arch_preset"] = K.CFG.get("arch_preset") or "none"


def _setup_cli(x):
    x.add_argument("action", nargs="?", choices=["show", "set", "check"]); x.add_argument("text", nargs="*")
    x.add_argument("--json", action="store_true"); x.add_argument("--path"); x.add_argument("--base")
    x.add_argument("--no-tools", dest="no_tools", action="store_true", help="只跑 evo 内置检查，不跑 import-linter / ruff 等外部工具")


class Preset:
    """服务 preset.arch：内核在 new / import 时用。"""
    NAMES = ARCH.NAMES

    @staticmethod
    def setup_notes(base, code, value):
        eff = ARCH.effective(base)
        notes = [f"架构预设 {value}：碰后端路径的件任务书里会带「架构规范」，交卷查结构（evo -p {code} arch 看全表）"]
        for t in ARCH.conflict_text(eff):
            notes.append("架构预设与现有结构不同，沿用现有、不迁移：" + t)
        return notes


def in_use(k, config):
    n = 0
    for code in k.list_projects():
        c = k._read_json(k._project_cfg_path(code))
        n += 1 if (c.get("arch_preset") or "none") != "none" else 0
    return n


def apply(ctx):
    global K
    K = ctx.k
    _ARCH.clear()
    ctx.provide("preset.arch", Preset)
    ctx.contribute("prompt.head", "20-arch", _head)
    ctx.contribute("delivery.check", "20-arch", arch_delivery_check)
    ctx.contribute("status", "arch_preset", _status)
    ctx.contribute("cli", "arch", {"help": "后端/架构预设：show | set <预设|键=值> | check", "setup": _setup_cli, "run": cmd_arch})
    ctx.subscribe("tick.before_dispatch", lambda ev: arch_conflicts_once(ev["live"]["s"]), priority=20, timeout=120)
