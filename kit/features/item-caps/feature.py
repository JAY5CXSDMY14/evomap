"""功能包 item-caps：每件上限（第十七轮老板决定③，第十八轮从内核搬出来）。

三个上限（0 = 关）：决策岗指导返工最多几次、一件最多派工几次、一件工人最多累计几小时；到了就暂停这件、开「继续 / 不做」老板闸门。
贡献：服务 caps（内核在决策岗返工、老板答闸门时用）、每轮检查（tick.after_dispatch）、status 的 limits、子命令 `evo limits`、
设置（App 设置页按 settings schema 自动画表单）。在用：有开着的上限闸门时关不掉（关了闸门就没人接）。
"""
import json
import os
import sys

import evo_time as TM

K = None
CONFIG = {}
CONFIG_SOURCE = {}
DEFAULTS_ = {"decider_reworks": 2, "item_hard_runs": 12, "item_hard_hours": 6}


CAP_KEYS = ("decider_reworks", "item_hard_runs", "item_hard_hours")


CAP_LABELS = {"decider_reworks": "决策岗指导返工最多几次（之后转老板）", "item_hard_runs": "一件最多派工几次（之后暂停等老板）",
              "item_hard_hours": "一件工人最多累计几小时（之后暂停等老板）"}


def cap(key):
    """一个上限的生效值（0 = 关）。层次：本项目 overrides.limits → features.yml 里本功能的设置（App 设置页 / evo limits set 不带 -p）
    → 全局 config.json 的 limits（老写法）→ manifest 默认。"""
    v = cap_value(key)[0]
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return float(DEFAULTS_[key])


def cap_value(key):
    """(值, 来源)：project / feature / global / default。"""
    if K.HAS_PROJECT and K._cfgp:
        ov = ((K._read_json(K._cfgp).get("overrides") or {}).get("limits") or {})
        if key in ov:
            return ov[key], "project"
    if CONFIG_SOURCE.get(key) == "user":
        return CONFIG[key], "feature"
    g = (K._read_json(K._global_path()).get("limits") or {})
    if key in g:
        return g[key], "global"
    return CONFIG.get(key, DEFAULTS_[key]), "default"


def open_budget_gate(s, k, it, why, rework=None):
    """上限到了：这件不再派工，建「继续 / 不做」老板闸门并立刻推送。rework：决策岗想要的返工说明，老板点继续就照它返工。"""
    if it.get("hold"):
        return it["hold"]
    c = K.coord(s)
    tid = K.EX.task_create(c, f"{k} 上限到了", why)
    q = f"{k} {it['title']}：{why}，继续还是不做？"[:200]
    gid = K.EX.gate_create(c, tid, q, ["继续", "不做"])
    s.setdefault("budget_gates", {})[gid] = {"key": k, "task": tid, "why": why, "rework": rework, "at": TM.now()}
    it["hold"] = gid
    s.setdefault("gate_since", {})[gid] = TM.now(); s.setdefault("gate_pushed", []).append(gid)     # 已推过，5 分钟提醒不重复
    K.tl(k, "gate_open", kind="budget", gate=gid, question=q)
    K.log(s, f"{k} {why}：暂停，等老板定继续还是不做")
    K.notify("gate_waiting", f"{k} {why}，继续还是不做？", it["title"], item=k, gate=gid, options=["继续", "不做"])
    return gid


def budget_answered(s, bud, choice, why):
    """老板答了上限闸门：继续 → 从现在起重新计数（决策岗那条照它的说明返工）；不做 → 这件不做。"""
    K.EX.task_update(K.coord(s), bud["task"], "completed")
    k = bud["key"]; it = s["items"].get(k)
    if not it:
        return
    it.pop("hold", None)
    if choice == "不做":
        K.drop_item(s, k, it, "老板：上限到了，不做" + (f"（{why}）" if why else ""))
        return K.gh_comment(it, "上限到了，老板决定不做。")
    u = it.get("usage") or {}
    it["budget_base"] = {"runs": u.get("runs", 0), "minutes": round(K.item_minutes(it), 1)}
    if bud.get("rework") is not None:
        it["decider_reworks"] = 0
        K.decide_rework(s, k, it, (bud["rework"] or "换个方案再做") + (f"\n老板：{why}" if why else ""), force=True)
    K.log(s, f"{k} 老板点了继续：上限从现在起重新计数")


def check_budget(s):
    """每轮：派工次数或工人累计小时到了上限（item_hard_runs / item_hard_hours，0 = 关）→ 暂停这件，推「继续还是不做」。"""
    mr, mh = cap("item_hard_runs"), cap("item_hard_hours")
    if not mr and not mh:
        return
    for k, it in s["items"].items():
        if it.get("hold") and it["state"] in K.QUIET_STATES + ("pushing",):
            # 在跑的那次已经把活干完了（或者不做了）：上限闸门作废
            K.EX.gate_resolve(K.coord(s), it["hold"], "作废（已完成）")
            K.mark_evo_resolved(s, it["hold"]); (s.get("budget_gates") or {}).pop(it["hold"], None); it.pop("hold")
            continue
        if it["state"] in K.QUIET_STATES + ("pushing",) or it.get("hold"):
            continue
        base = it.get("budget_base") or {}
        runs = (it.get("usage") or {}).get("runs", 0) - base.get("runs", 0)
        mins = K.item_minutes(it) - base.get("minutes", 0)
        if mr and runs >= mr:
            open_budget_gate(s, k, it, f"已派工 {runs} 次还没完")
        elif mh and mins >= mh * 60:
            h = mins / 60
            open_budget_gate(s, k, it, f"已烧 {h:.0f} 小时还没完" if h >= 1 else f"已烧 {mins:.0f} 分钟还没完")


def cmd_limits(a):
    """每件上限（老板决定③）：evo [-p 代号] limits [show | set 键=值 …] [--json]。没 -p 改全局；-p 改本项目（overrides.limits）。
    键：decider_reworks（决策岗指导返工最多几次）、item_hard_runs（一件最多派工几次）、item_hard_hours（一件工人最多累计几小时）；0 = 关。"""
    if a.action == "set":
        K.refuse_agents("改上限")
        kv = {}
        for t in a.text or []:
            k, _, v = t.partition("=")
            if k not in CAP_KEYS:
                sys.exit(f"只能改：{', '.join(CAP_KEYS)}")
            try:
                n = float(v)
            except ValueError:
                sys.exit(f"{k} 要写数字（0 = 关）")
            if n < 0 or n > 1000:
                sys.exit(f"{k} 要在 0–1000 之间")
            kv[k] = int(n) if n == int(n) else n
        if not kv:
            sys.exit("用法：evo [-p 代号] limits set decider_reworks=2 item_hard_runs=12 item_hard_hours=6")
        if K.HAS_PROJECT and K._cfgp:
            raw = K._read_json(K._cfgp); ov = raw.setdefault("overrides", {}); ov.setdefault("limits", {}).update(kv)
            json.dump(raw, open(K._cfgp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        else:                                          # 第十八轮：全局的上限存 features.yml（App 设置页的自动表单同此）
            K.rt().set_config("item-caps", kv)
            CONFIG.update(kv); CONFIG_SOURCE.update({k: "user" for k in kv})
    doc = {"schema_version": K.APP_SCHEMA_VERSION, "project": K.CODE if K.HAS_PROJECT else None,
           "limits": limits_doc(), "labels": CAP_LABELS, "source": {k: cap_value(k)[1] for k in CAP_KEYS}}
    if a.json:
        print(json.dumps(doc, ensure_ascii=False)); return
    print(f"每件上限（{'项目 ' + K.CODE if K.HAS_PROJECT else '全局'}；0 = 关）")
    for k in CAP_KEYS:
        print(f"  {k} = {doc['limits'][k]}   {CAP_LABELS[k]}")



def limits_doc():
    out = {}
    for k in CAP_KEYS:
        v = cap_value(k)[0]
        try:
            f = float(v)
            out[k] = int(f) if f == int(f) else f
        except (TypeError, ValueError):
            out[k] = DEFAULTS_[k]
    return out


class Caps:
    """服务 caps。"""
    get = staticmethod(cap)
    answered = staticmethod(budget_answered)
    open_gate = staticmethod(open_budget_gate)

    @staticmethod
    def over_decider(s, k, it, note):
        """决策岗又要返工：到上限了就开老板闸门并返回 True（内核就不返工了）。"""
        lim = cap("decider_reworks")
        if lim and it.get("decider_reworks", 0) >= lim:
            open_budget_gate(s, k, it, f"决策岗已指导返工 {it.get('decider_reworks', 0)} 次还没好", rework=note or "换个方案再做")
            return True
        return False


def _status(s, doc):
    doc["limits"] = limits_doc()


def _setup_cli(x):
    x.add_argument("action", nargs="?", choices=["show", "set"]); x.add_argument("text", nargs="*"); x.add_argument("--json", action="store_true")


def in_use(k, config):
    n = 0
    for code in k.list_projects():
        p = os.path.join(k.HOME_DIR, code, "state", "state.json")
        try:
            st = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        n += len(st.get("budget_gates") or {})
    return n


def apply(ctx):
    global K
    K = ctx.k
    CONFIG.clear(); CONFIG.update(ctx.config)
    CONFIG_SOURCE.clear(); CONFIG_SOURCE.update(K.rt().features["item-caps"].config_source)
    ctx.provide("caps", Caps)
    ctx.contribute("status", "limits", _status)
    ctx.contribute("cli", "limits", {"help": "每件上限：show | set decider_reworks=2 item_hard_runs=12 item_hard_hours=6",
                                     "setup": _setup_cli, "run": cmd_limits, "no_project": True})
    ctx.subscribe("tick.after_dispatch", lambda ev: check_budget(ev["live"]["s"]), priority=30, timeout=300)
