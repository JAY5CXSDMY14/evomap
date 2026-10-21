"""功能包 ui-preset：UI 栈预设（第十五轮的 evo_ui，第十八轮从内核搬出来）。

贡献：任务书开头的「UI 规范」（prompt.head）、交卷依赖检查（delivery.check）、每轮一次的冲突提示（tick.before_dispatch）、
status --json 的 ui_preset 字段（status）、子命令 `evo ui`（cli）、服务 preset.ui（new/import 的 --ui-preset 用）。
只经内核接口 K 和事件说话，不 import 别的功能包。
"""
import json
import os
import re
import sys

import evo_ui as UI

K = None          # 内核接口（apply / in_use 时填上）


_UI = {}


def ui_eff():
    """本项目实际生效的 UI 规范（ui_preset=none 时 None）。一个进程算一次；预设文件坏了只提示、不拦接棒。"""
    if "eff" not in _UI:
        try:
            _UI["eff"] = UI.effective(K.CFG)
        except (ValueError, OSError) as e:
            print(f"UI 预设读不出：{e}", file=sys.stderr)
            _UI["eff"] = None
    return _UI["eff"]


def ui_conflicts_once(s):
    """仓库某一类已经在用别的库（现有的赢）：日志 + 提醒各一次；冲突内容变了再报。"""
    eff = ui_eff()
    sig = UI.conflict_sig(eff) if eff and eff["conflicts"] else ""
    if sig and s.get("ui_reported") != sig:
        txt = "；".join(UI.conflict_text(eff))
        K.log(s, f"UI 预设 {eff['name']} 与仓库现有栈有冲突，现有的赢、不迁移：{txt}")
        K.notify("ui_conflict", "UI 预设：仓库现有栈优先", txt)
    if sig or s.get("ui_reported"):
        s["ui_reported"] = sig


def ui_delivery_check(s, k, it):
    """施工交卷后、送验收前：对比本件改动前后的依赖清单。新加禁用库/同类第二个库 → 返回打回原因；
    lockfile 里才有的、手写了预设已有的组件、新依赖没在交卷里说明 → 只记提示（时间线 ui_advisory），不拦。"""
    eff = ui_eff(); wt = it.get("worktree")
    if not eff or not wt:
        return None
    base = K.git(wt, "merge-base", K.CFG["main_branch"], "HEAD", check=False)
    if not base:
        return None
    eff = UI.effective(K.CFG, present=UI.git_deps(wt, base)["manifest"])   # 「现有」按改动前的主线算
    r = UI.check(wt, base, "HEAD", eff)
    rep = json.dumps(it.get("report") or {}, ensure_ascii=False)
    unexplained = [p for p in r["new_deps"] if p not in rep]
    notes = [f"lockfile 新出现禁用库 {x['package']}（{x['label']}，可能是传递依赖）" for x in r["lock_only"]] + \
            [f"新文件 {x['path']} 像是手写的 {x['component']}，预设里已有（{eff['component_dir'] or '系统组件'}）" for x in r["handrolled"]] + \
            [f"新依赖 {p} 不在 UI 规范里，交卷没写理由" for p in unexplained]
    if notes:
        it["ui_notes"] = notes
        K.tl(k, "ui_advisory", notes=notes)
        K.log(s, f"{k} UI 规范提示：" + "；".join(notes)[:200])
    if r["violations"]:
        return ("新加了 UI 规范不允许的依赖：" + UI.violation_text(r["violations"]) +
                "。改用规范里的库并删掉这个依赖；确实要换，先 ask 决策岗，老板批准后写进项目 ui_overrides")
    return None


def cmd_ui(a):
    """evo -p AB ui [show]：看本项目生效的 UI 规范；ui set <预设> / set 类别=包名 / set 类别=：改（外部 Agent 不能改）；
    ui check [--path 目录] [--base 提交]：在工作区对比依赖，有禁用库退出码 1（验收岗用）。"""
    act = a.action or "show"
    if act == "show":
        pv = (a.text or [None])[0]               # ui show web-react：不改配置，先看这个预设套到本仓库会怎样
        if pv and pv not in UI.NAMES:
            sys.exit(f"UI 预设只能是：{' | '.join(UI.NAMES)}")
        eff = UI.effective({**K.CFG, "ui_preset": pv}) if pv else ui_eff()
        if a.json:
            print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, "ui_preset": K.CFG.get("ui_preset") or "none", "effective": eff}, ensure_ascii=False, indent=1)); return
        print(UI.table(eff) if eff else "UI 预设：none（没开；evo -p " + K.CODE + " ui set web-react | swiftui）"); return
    if act == "check":
        path = a.path or (os.getcwd() if K.git(os.getcwd(), "rev-parse", "--git-dir", check=False) else K.CFG["repo"])
        if not ui_eff():
            print("UI 预设：none，不查"); return
        base = a.base or K.git(path, "merge-base", K.CFG["main_branch"], "HEAD", check=False) or "HEAD"
        eff = UI.effective(K.CFG, present=UI.git_deps(path, base)["manifest"])   # 「现有」按改动前算，新加的不算现有
        r = UI.check(path, base, "HEAD", eff)
        if a.json:
            print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, **r}, ensure_ascii=False, indent=1))
        else:
            print(f"UI 依赖检查（预设 {eff['name']}，对比 {base[:10]}..HEAD）")
            for x in r["violations"]:
                print(f"  ✗ 不合规：{x['label']}已定「{x['choice']}」，新加了 {x['package']}")
            for x in r["lock_only"]:
                print(f"  ! 提示：lockfile 新出现禁用库 {x['package']}（{x['label']}，可能是传递依赖，核对一下）")
            for p in r["new_deps"]:
                print(f"  ? 新依赖 {p} 不在规范里：交卷 changes 里要写明为什么")
            for x in r["handrolled"]:
                print(f"  ! 建议：{x['path']} 像是手写的 {x['component']}，预设里已有，优先用现成组件")
            for t in UI.conflict_text(eff):
                print("  · 现有栈优先：" + t)
            if not any(r.values()):
                print("  ✓ 没有问题")
        sys.exit(1 if r["violations"] else 0)
    K.refuse_agents("改 UI 预设")
    arg = " ".join(a.text or []).strip()
    if not arg:
        sys.exit("用法：evo ui set web-react | swiftui | none，或 evo ui set 类别=包名[,包名]（类别= 清掉）")
    c = K._read_json(K._project_cfg_path(K.CODE))
    if "=" in arg:
        cat, _, val = arg.partition("=")
        cat = cat.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", cat):
            sys.exit("类别名只许小写字母、数字、- _（例 icons）")
        pk = [x.strip() for x in val.split(",") if x.strip()]
        if any(not re.fullmatch(r"[@A-Za-z0-9._/*+-]{1,80}", x) for x in pk):
            sys.exit("包名只许字母数字和 @ . _ / * + -")
        ov = dict(c.get("ui_overrides") or {})
        if pk:
            ov[cat] = pk
        else:
            ov.pop(cat, None)
        if ov:
            c["ui_overrides"] = ov
        else:
            c.pop("ui_overrides", None)
        K._write_project_cfg(c)
        print(f"{K.CODE} UI 覆盖：{cat} = {'、'.join(pk) if pk else '（已清掉，回到预设）'}。下一份任务书起生效")
        return
    if arg not in UI.NAMES:
        sys.exit(f"UI 预设只能是：{' | '.join(UI.NAMES)}")
    if arg == "none":
        c.pop("ui_preset", None)
    else:
        c["ui_preset"] = arg
    K._write_project_cfg(c)
    print(f"{K.CODE} UI 预设：{arg}。下一份任务书起生效（只管新代码，旧栈不迁移）")
    eff = UI.effective({**K.CFG, **c})
    for t in UI.conflict_text(eff) if eff else []:
        print("  · 现有栈优先：" + t)



def _head(role, it):
    return UI.head(role, it, ui_eff(), K.CODE)


def _status(s, doc):
    doc["ui_preset"] = K.CFG.get("ui_preset") or "none"


def _setup_cli(x):
    x.add_argument("action", nargs="?", choices=["show", "set", "check"]); x.add_argument("text", nargs="*")
    x.add_argument("--json", action="store_true"); x.add_argument("--path"); x.add_argument("--base")


class Preset:
    """服务 preset.ui：内核在 new / import 时用。"""
    NAMES = UI.NAMES

    @staticmethod
    def setup_notes(base, code, value):
        eff = UI.effective(base)
        notes = [f"UI 预设 {value}：碰界面的件任务书里会带「UI 规范」，验收查依赖（evo -p {code} ui 看全表）"]
        for t in UI.conflict_text(eff):
            notes.append("UI 预设与现有栈冲突，现有的赢、不迁移：" + t)
        return notes


def in_use(k, config):
    n = 0
    for code in k.list_projects():
        c = k._read_json(k._project_cfg_path(code))
        n += 1 if (c.get("ui_preset") or "none") != "none" else 0
    return n


def apply(ctx):
    global K
    K = ctx.k
    _UI.clear()
    ctx.provide("preset.ui", Preset)
    ctx.contribute("prompt.head", "10-ui", _head)
    ctx.contribute("delivery.check", "10-ui", ui_delivery_check)
    ctx.contribute("status", "ui_preset", _status)
    ctx.contribute("cli", "ui", {"help": "UI 栈预设：show | set <预设|类别=包名> | check", "setup": _setup_cli, "run": cmd_ui})
    ctx.subscribe("tick.before_dispatch", lambda ev: ui_conflicts_once(ev["live"]["s"]), priority=10, timeout=120)
