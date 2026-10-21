#!/usr/bin/env python3
"""CI 录屏用的假 evo：只认应用会调的几个命令，状态存在 $EVO_DEMO_STATE（JSON，从 demo-state.json 拷一份）。
不碰 git、不碰网络。时间字段按「现在往前推几分钟」现算，截图里永远是新鲜的。"""
import json, os, sys, time, datetime as dt

STATE = os.environ.get("EVO_DEMO_STATE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo-state.json")


def now():
    return dt.datetime.now(dt.timezone.utc).astimezone()


def ago(m):
    t = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=m)
    # 标准 ISO 8601（应用用 ISO8601DateFormatter 解析）；手拼，不依赖 strftime 的本地化
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (t.year, t.month, t.day, t.hour, t.minute, t.second)


def load():
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)


def save(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def out(o):
    print(json.dumps(o, ensure_ascii=False))


def status(s, code):
    p = s["projects"][code]
    doc = {k: v for k, v in p.items() if k not in ("tick_ago", "logs")}
    doc["schema_version"] = 1
    doc["project"] = code
    doc["generated_at"] = ago(0)
    doc["last_tick"] = ago(p.get("tick_ago", 1))
    doc["gates"] = [dict(g, waiting_since=ago(g.pop("ago", 5)) if "ago" in g else g.get("waiting_since")) for g in
                    [dict(x) for x in p.get("gates", [])]]
    return doc


TEAM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team.json")
ROLE = {"build": "施工", "verify": "验收", "decide": "决策"}


def team(s, argv):
    """evo team --json / set <岗位> --model X [--thinking L] [--project P] / dismiss X / init --json|--apply。改动记在状态文件 team_changes。"""
    act = argv[0] if argv and not argv[0].startswith("-") else "show"
    ch = s.setdefault("team_changes", {})
    def opt(name):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None
    if act == "show":
        d = json.load(open(TEAM, encoding="utf-8"))
        for c in d["cards"]:
            o = ch.get(c["role"]) or {}
            if o.get("model"):
                c["models"] = [o["model"]]
                if c["recommendation"].get("switch_to") == o["model"]:
                    c["recommendation"] = {"text": f"刚换成 {o['model']}，攒够 5 次再比。", "switch_to": None}
            if o.get("thinking"):
                c["thinking"] = o["thinking"]
        if s.get("team_dismissed"):
            d["suggestions"] = []
        out(d); return 0
    if act == "set":
        role = argv[1]
        time.sleep(0.6)
        o = ch.setdefault(role, {})
        if opt("--model"):
            o["model"] = opt("--model")
        if opt("--thinking"):
            o["thinking"] = opt("--thinking")
        save(s)
        where = f"{opt('--project')} 本项目专用" if opt("--project") else "全局"
        print(f"{ROLE.get(role, role)}（{where}）：{o.get('model') or '原模型'}。下一次派工生效，正在跑的不打断。")
        return 0
    if act == "dismiss":
        s["team_dismissed"] = True; save(s); print("已收起"); return 0
    if act == "trial":
        print(f"{ROLE.get(argv[1], argv[1])}在 {opt('--project')} 试用 {argv[2]}，满 5 件给你对比。"); return 0
    if act == "init":
        if "--apply" in argv:
            print(json.dumps({"ok": True, "applied": ["build", "verify", "decide"], "notes": []})); return 0
        out({"cards": {"build": {"tool": "codex", "models": [], "thinking": "medium", "fallback": {"tool": "dsh", "models": ["group/evo-build"]}},
                       "verify": {"tool": "claude", "models": [], "thinking": "high", "fallback": {"tool": "dsh", "models": ["group/evo-verify"]}},
                       "decide": {"tool": "claude", "models": [], "thinking": "high"}},
             "notes": [], "magpie": {"ok": True, "groups": ["group/evo-build", "group/evo-verify"]}})
        return 0
    print("假 evo team：不认得 " + " ".join(argv), file=sys.stderr); return 1


FEATURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "features.json")


def builtin_feature(s, argv):
    """没有真 evo 时的 evo feature：list --json / on / off / set（只认 features.json 里的设置，按 schema 校验）。"""
    d = json.load(open(FEATURES, encoding="utf-8"))
    ch = s.setdefault("features", {})
    for f in d["features"]:
        o = ch.get(f["id"]) or {}
        if "enabled" in o:
            f["enabled"] = o["enabled"]; f["state"] = "active" if o["enabled"] else "off"; f["why"] = "" if o["enabled"] else "你关了它"
        f["config"].update(o.get("config") or {})
    act = argv[0] if argv else "list"
    if act in ("list", "dump"):
        out(d); return 0
    f = next((x for x in d["features"] if len(argv) > 1 and x["id"] == argv[1]), None)
    if not f:
        print(f"没有功能 {argv[1] if len(argv) > 1 else ''}", file=sys.stderr); return 2
    o = ch.setdefault(f["id"], {})
    if act in ("on", "off"):
        if act == "off" and f.get("in_use"):
            print(f"{f['id']} 正在用（{f['in_use_text']}），关不掉", file=sys.stderr); return 2
        o["enabled"] = act == "on"; save(s); print(f"{f['id']} 已{'开' if act == 'on' else '关'}"); return 0
    if act == "set":
        props = (f.get("settings") or {}).get("properties") or {}
        for kv in argv[2:]:
            k, _, v = kv.partition("=")
            p = props.get(k)
            if not p:
                print(f"{f['id']} 没有设置 {k}", file=sys.stderr); return 2
            try:
                val = {"integer": int, "number": float, "boolean": lambda x: x in ("true", "1", "on"), "string": str}[p["type"]](v)
            except ValueError:
                print(f"{k} 要是 {p['type']}", file=sys.stderr); return 2
            if p["type"] in ("integer", "number") and not (p.get("minimum", -1e18) <= val <= p.get("maximum", 1e18)):
                print(f"{k} 要在 {p.get('minimum')}–{p.get('maximum')} 之间", file=sys.stderr); return 2
            o.setdefault("config", {})[k] = val
        save(s); print(f"{f['id']} 设置已存"); return 0
    print("用法：feature list|on|off|set", file=sys.stderr); return 2


def main(argv):
    s = load()
    code = None
    if len(argv) >= 2 and argv[0] == "-p":
        code, argv = argv[1], argv[2:]
    cmd = argv[0] if argv else "help"
    if cmd in ("plugin", "feature", "watch"):
        # v0.6.0 插件、v0.7.0 功能开关 / 事件流：交给真 evo（包里的 kit；$EVO_HOME、$EVO_PLUGINS_DIR 指到临时目录），演示的是真机制
        real = os.environ.get("EVO_REAL_EVO")
        if not real or not os.path.exists(real):
            if cmd == "feature":
                return builtin_feature(s, argv[1:])
            print(f"假 evo：没有 EVO_REAL_EVO，{cmd} 演示不了", file=sys.stderr); return 2
        os.execv(sys.executable, [sys.executable, real] + argv)
    if cmd == "_demo":                   # v0.7.0：演示用开关：_demo break log / _demo fix log（让 evo log 失败，看错误卡片）
        act, what = (argv[1:3] + ["", ""])[:2]
        broken = set(s.get("broken") or [])
        if act == "break":
            broken.add(what)
        elif act == "fix":
            broken.discard(what)
        s["broken"] = sorted(broken); save(s)
        print(f"演示：{what} {'坏了' if what in broken else '好了'}"); return 0
    if cmd in (s.get("broken") or []):
        print(f"evo {cmd} 读状态文件失败：state.json 被锁住（演示）", file=sys.stderr); return 1
    if cmd == "projects" and "--json" in argv:
        out({"schema_version": 1, "projects": [{"code": c, "name": p["name"]} for c, p in s["projects"].items()]})
        return 0
    if cmd == "projects":
        for c, p in s["projects"].items():
            print(f"{c} {p['name']} ~/code/{c.lower()} JAY5CXSDMY14/{c.lower()}")
        return 0
    if cmd == "status":
        out(status(s, code)); return 0
    if cmd == "approve":
        gid, choice = argv[1], argv[2]
        words = argv[3] if len(argv) > 3 else ""
        p = s["projects"][code]
        g = next((g for g in p["gates"] if g["id"] == gid), None)
        if not g:
            print(f"没有闸门 {gid}", file=sys.stderr); return 1
        time.sleep(0.6)
        p["gates"] = [x for x in p["gates"] if x["id"] != gid]
        first = (g.get("options") or ["通过"])[0]
        ev = {"at": ago(0), "event": "gate_approve" if choice == first else "gate_reject", "choice": choice}
        if words:
            ev["words"] = words
        if g.get("item"):
            p.setdefault("logs", {}).setdefault(g["item"], {"key": g["item"], "events": []})["events"].append(ev)
        if choice == first:
            p.setdefault("count", {})["merged"] = p.get("count", {}).get("merged", 0) + 1
        save(s)
        print(f"好的：{gid} → {choice}")
        return 0
    if cmd == "log":
        key = argv[1]
        argv = [a for a in argv if a != "--json"]
        p = s["projects"][code]
        l = (p.get("logs") or {}).get(key)
        it = next((i for i in p.get("items", []) if i["key"] == key), None)
        if not l and not it:
            print(f"没有 {key}", file=sys.stderr); return 1
        l = dict(l or {"key": key, "events": []})
        l.setdefault("title", (it or {}).get("title"))
        l.setdefault("state", (it or {}).get("state"))
        l.setdefault("raw", (it or {}).get("raw"))
        # 相对时间 → 绝对时间
        evs = []
        for e in l.get("events", []):
            e = dict(e)
            if "ago" in e:
                e["at"] = ago(e.pop("ago"))
            e["item"] = key
            evs.append(e)
        l["events"] = evs
        out(l); return 0
    if cmd == "feedback":
        time.sleep(1.2)
        print("https://github.com/JAY5CXSDMY14/tubu-platform/issues/42"); return 0
    if cmd == "add":
        time.sleep(0.8); print(f"{code}-FEAT-005 已登记"); return 0
    if cmd in ("tick", "ship"):
        time.sleep(1.5); print("转了一轮"); return 0
    if cmd == "team":                    # v0.4.0 团队页：岗位卡片（scripts/demo/team.json）+ 换模型
        return team(s, argv[1:])
    if cmd == "watchdog":
        print("都在转"); return 0
    if cmd == "panel":
        print("token: demo-token"); return 0
    print("假 evo：不认得 " + " ".join(argv)); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
