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


def main(argv):
    s = load()
    code = None
    if len(argv) >= 2 and argv[0] == "-p":
        code, argv = argv[1], argv[2:]
    cmd = argv[0] if argv else "help"
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
    if cmd == "watchdog":
        print("都在转"); return 0
    if cmd == "panel":
        print("token: demo-token"); return 0
    print("假 evo：不认得 " + " ".join(argv)); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
