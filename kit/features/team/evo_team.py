"""模型协调（第十四轮）：岗位卡片、健康检查、备用切换、模型质量统计、新模型发现。

设计见 docs/model-coordination.md。这里只放「算」的逻辑和本机小文件的读写；接棒器 evo 在派工、额度、状态几处调用。
- 岗位卡片 = roles.<岗位> 里的 tool / via / cmd / models / thinking / duty / fallback{tool,cmd,models,thinking,account}。
- 模型只从 magpie（GET /v1/models）来；evo 不存任何密钥。外部 CLI（claude、codex、dsh、pi）用它自己的登录和模型。
- 健康检查结果缓存 5 分钟：~/.evoloop/team_health.json；见过的 magpie 模型记在 ~/.evoloop/team_models.json。
"""
import fcntl, json, os, re, shlex, shutil

ROLE_NAMES = {"build": "施工", "verify": "验收", "decide": "决策"}
CARD_ROLES = ("build", "verify", "decide")
THINKING = ("off", "low", "medium", "high", "max")
HEALTH_TTL = 300                       # 健康检查缓存 5 分钟
KNOWN_TOOLS = ("claude", "codex", "dsh", "pi")
# 「是否已登录」只是猜：看这些文件在不在（相对 HOME）。不认识的工具不猜。
LOGIN_FILES = {"claude": [".claude/.credentials.json", ".claude.json"], "codex": [".codex/auth.json"]}
STRONG_RE = re.compile(r"opus|gpt-5(?!.*(mini|nano|flash))|(^|[/-])o3|\bpro\b|-pro|max|ultra|reasoner|r1|group/evo-decide", re.I)
MIN_SAMPLE = 5                         # 少于 5 件不下结论
STATUS_LABELS = {"ok": "可用", "fallback": "用备用中", "not_installed": "没装", "not_logged_in": "未登录",
                 "rate_limited": "额度满", "retired": "模型已下线", "unknown_model": "模型不认识", "overlap": "和施工撞模型",
                 "magpie_down": "magpie 不通", "off": "没配置"}


# 第十八轮：岗位卡片的基础（命令模板、tool_of、via_of、render_cmd、fallback_rc、account_of）派工也要用，搬进内核库 kit/bin/evo_roles.py
from evo_roles import TOOL_CMDS, tool_of, cmd_tool, via_of, render_cmd, fallback_rc, account_of  # noqa: F401


# ---------- 小工具 ----------
def _rw(path, fn):
    """在锁里读改写一个小 JSON 文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            d = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        except ValueError:
            d = {}
        r = fn(d)
        tmp = path + ".tmp"
        json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return r


def _read(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ---------- 健康检查（缓存 5 分钟）----------
def health_path(root):
    return os.path.join(root, "team_health.json")


def registry_path(root):
    return os.path.join(root, "team_models.json")


def _probe_path(home):
    """Air 试跑 10-21：在没有 ~/.local/bin 的 shell 里刷新，会把 claude 误判成「没装」并缓存 5 分钟。
    除了当前 PATH，再看常见安装目录（和 install.sh 写给常驻进程的 PATH 一致的那几处）。"""
    extra = [os.path.join(home, ".local", "bin"), "/opt/homebrew/bin", "/usr/local/bin", os.path.join(home, ".npm-global", "bin"),
             os.path.join(home, ".claude", "local")]
    seen, out = set(), []
    for d in (os.environ.get("PATH") or "").split(os.pathsep) + extra:
        if d and d not in seen:
            seen.add(d); out.append(d)
    return os.pathsep.join(out)


def probe_clis(home, tools=None):
    """本机装了哪些 CLI、看起来登录了没有（只是猜）。"""
    out = {}
    for t in list(KNOWN_TOOLS) + [x for x in (tools or {}) if x not in KNOWN_TOOLS]:
        tc = (tools or {}).get(t) or {}
        path = shutil.which(tc.get("bin") or t, path=_probe_path(home))
        files = tc.get("login_files") or LOGIN_FILES.get(t)
        logged = None if not files else any(os.path.exists(os.path.join(home, f)) for f in files)
        out[t] = {"installed": bool(path), "path": path, "logged_in": logged if path else None}
    return out


def parse_models(data):
    """magpie /v1/models（OpenAI 格式）→ [{id, members, retired, tier}]；不是这个格式返回 None。"""
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return None
    out = []
    for m in data["data"]:
        if not isinstance(m, dict) or not isinstance(m.get("id"), str):
            continue
        mem = m.get("members") or m.get("models")
        retired = bool(m.get("retired") or m.get("deprecated") or str(m.get("status") or "").lower() in ("retired", "deprecated", "offline"))
        out.append({"id": m["id"], "members": [x for x in mem if isinstance(x, str)] if isinstance(mem, list) else None,
                    "retired": retired, "tier": m.get("tier")})
    return out


def health(root, home, magpie_url, http, now, tools=None, force=False):
    """返回 (健康表, 新事件列表)。新事件只在真正刷新的那次产生：magpie 由通变不通 / 不通变通、新模型出现、模型下线。"""
    events = []

    def f(d):
        if not force and d.get("at") and 0 <= now - d["at"] < HEALTH_TTL:
            return dict(d)
        url = (magpie_url or "http://127.0.0.1:3425").rstrip("/") + "/v1/models"
        try:
            code, data = http(url, timeout=3)
            listed = parse_models(data) if code == 200 else None
        except Exception:
            listed = None
        was = (d.get("magpie") or {}).get("ok")
        d.clear()
        d.update({"at": now, "magpie": {"ok": listed is not None, "url": url, "models": listed},
                  "clis": probe_clis(home, tools)})
        if was is True and listed is None:
            events.append(("magpie_down", {"url": url}))
        if was is False and listed is not None:
            events.append(("magpie_up", {"url": url}))
        if listed is not None:
            events.extend(_registry_update(root, listed, now))
        return dict(d)
    return _rw(health_path(root), f), events


def _registry_update(root, listed, now):
    """记下见过的 magpie 模型：第一次只记、不提醒；之后新出现的合成一条「新模型可用」，不见了的记「已下线」。"""
    ids = [m["id"] for m in listed]
    ev = []

    def f(d):
        known = d.setdefault("known", {})
        first = not known
        new = [i for i in ids if i not in known]
        for i in ids:
            known.setdefault(i, {"first_seen": now})
            known[i]["last_seen"] = now
            known[i].pop("gone", None)
        gone = [i for i, e in known.items() if i not in ids and not e.get("gone")]
        for i in gone:
            known[i]["gone"] = now
        if new and not first:
            sug = d.setdefault("suggestions", [])
            sug.extend({"model": i, "at": now} for i in new if i not in [x["model"] for x in sug])
            ev.append(("model_new", {"models": new}))
        if gone:
            ev.append(("model_gone", {"models": gone}))
    _rw(registry_path(root), f)
    return ev


def registry(root):
    return _read(registry_path(root))


def dismiss_suggestion(root, model):
    def f(d):
        before = len(d.get("suggestions") or [])
        d["suggestions"] = [x for x in d.get("suggestions") or [] if x["model"] != model]
        return before != len(d["suggestions"])
    return _rw(registry_path(root), f)


def members(model, h):
    """一个模型名展开成实际模型：magpie 列表里这个组带了成员就用成员，否则就是它自己。"""
    if not model:
        return set()
    listed = ((h or {}).get("magpie") or {}).get("models") or []
    e = next((m for m in listed if m["id"] == model), None) or {}
    return set(e.get("members") or []) or {model}


def model_problem(model, rc, h, reg, tools=None):
    """这个模型现在能不能派工。返回 None 或 (代号, 说明)。只在能判断时才判：magpie 不通不判 magpie 模型。"""
    if not model:
        return None
    via = via_of(rc)
    if via == "magpie":
        mg = (h or {}).get("magpie") or {}
        if not mg.get("ok"):
            return None
        e = next((m for m in mg.get("models") or [] if m["id"] == model), None)
        if e and e.get("retired"):
            return ("retired", f"模型 {model} 在 magpie 里标了已下线")
        if not e:
            gone = ((reg or {}).get("known") or {}).get(model, {}).get("gone")
            if gone:
                return ("retired", f"模型 {model} 已从 magpie 下线（列表里不见了）")
            return ("unknown_model", f"模型 {model} 不在 magpie 的模型列表里（名字写错了，或还没在 magpie 里配）")
        return None
    cat = ((tools or {}).get(tool_of(rc)) or {}).get("models")
    if isinstance(cat, list) and cat:
        names = {x if isinstance(x, str) else x.get("id") for x in cat}
        retired = {x.get("id") for x in cat if isinstance(x, dict) and x.get("retired")}
        if model in retired:
            return ("retired", f"{tool_of(rc)} 的模型 {model} 已下线")
        if model not in names:
            return ("unknown_model", f"{tool_of(rc)} 的模型列表里没有 {model}")
    return None


def usable_models(rc, h, reg, tools=None):
    """卡片里能用的模型（保持顺序）和第一个问题（全不能用时给出原因）。没写模型 = 用工具默认，算能用。"""
    ms = list((rc or {}).get("models") or [])
    if not ms:
        return [None], None
    ok, first = [], None
    for m in ms:
        p = model_problem(m, rc, h, reg, tools)
        if p:
            first = first or p
        else:
            ok.append(m)
    return ok, (None if ok else first)


def route(role, rc, h, reg, paused, fb_paused, build_model=None, tools=None):
    """这次派工走主模型还是备用。返回 (路线 "primary"/"fallback" 或 None, 原因代号, 说明, 可用模型)。
    顺序：主模型能用就用主；不能用（额度满 / magpie 不通 / 模型下线或不认识 / 和施工撞模型）且备用能用 → 备用；都不行 → 停这个岗位。"""
    def check(card, is_paused):
        if not card:
            return ("off", "没配置备用", [])
        if is_paused:
            return ("rate_limited", "额度满", [])
        if via_of(card) == "magpie" and not ((h or {}).get("magpie") or {}).get("ok", True):
            return ("magpie_down", "magpie 不通（这张卡的模型走 magpie）", [])
        ms, prob = usable_models(card, h, reg, tools)
        if prob:
            return (prob[0], prob[1], [])
        if role == "verify" and build_model:
            bm = members(build_model, h)
            ms2 = [m for m in ms if m is None or not (members(m, h) & bm)]
            if not ms2:
                return ("overlap", f"验收的模型和施工这次用的 {build_model} 撞了（含 magpie 组成员）：验收必须换一个模型", [])
            ms = ms2
        return (None, None, ms)
    code, why, ms = check(rc, paused)
    if code is None:
        return "primary", None, None, ms
    fb = fallback_rc(rc, tools)
    fcode, fwhy, fms = check(fb, fb_paused)
    if fb and fcode is None:
        return "fallback", code, why, fms
    return None, code, why + (f"；备用也不行：{fwhy}" if fb and fwhy else ""), []


def is_strong(model, h=None, tiers=None):
    if not model:
        return None
    t = (tiers or {}).get(model)
    if t is None:
        e = next((m for m in (((h or {}).get("magpie") or {}).get("models") or []) if m["id"] == model), None) or {}
        t = e.get("tier")
    if t is not None:
        return str(t).lower() in ("strong", "top", "expensive", "high")
    return bool(STRONG_RE.search(model))


def card_warnings(role, rc, h, reg, tools=None, other=None, tiers=None):
    """卡片上的提醒（不拦派工）：列表里有下线/不认识的模型、施工和验收配置上就撞了、决策岗没用贵模型。"""
    out = []
    for m in (rc or {}).get("models") or []:
        p = model_problem(m, rc, h, reg, tools)
        if p:
            out.append(p[1])
    if role == "verify" and other is not None:
        b = set().union(*[members(m, h) for m in other.get("models") or []]) if other.get("models") else set()
        v = set().union(*[members(m, h) for m in rc.get("models") or []]) if rc.get("models") else set()
        if b & v:
            out.append(f"施工和验收的模型有重叠（{', '.join(sorted(b & v))}）：碰上同一个时验收会停下等你换")
    if role == "decide" and (rc or {}).get("cmd"):
        ms = rc.get("models") or []
        if ms and not any(is_strong(m, h, tiers) for m in ms):
            out.append(f"决策岗建议用最强（贵）的模型，现在是 {', '.join(ms)}")
    return out


def health_status(role, rc, h, rl_entry, now, tools=None, reg=None):
    """状态灯：可用 / 用备用中 / 没装 / 未登录 / 额度满（恢复时间）/ 模型已下线 / magpie 不通。"""
    if not (rc or {}).get("cmd"):
        return {"code": "off", "label": STATUS_LABELS["off"]}
    clis = (h or {}).get("clis") or {}
    tool = tool_of(rc)
    paused = bool(rl_entry and rl_entry.get("until", 0) > now)
    rt, code, why, _ = route(role, rc, h, reg, paused, False, tools=tools)
    if rt == "fallback":
        st = {"code": "fallback", "label": STATUS_LABELS["fallback"], "why": why}
        if paused:
            st["until"] = rl_entry["until"]
        return st
    if paused:
        return {"code": "rate_limited", "label": STATUS_LABELS["rate_limited"], "until": rl_entry["until"], "why": (rl_entry.get("why") or "")[:120]}
    if code:
        return {"code": code, "label": STATUS_LABELS.get(code, code), "why": why}
    c = clis.get(tool)
    if c and not c["installed"]:
        return {"code": "not_installed", "label": STATUS_LABELS["not_installed"], "why": f"本机找不到 {tool} 命令"}
    if c and c.get("logged_in") is False:
        return {"code": "not_logged_in", "label": STATUS_LABELS["not_logged_in"], "why": f"没找到 {tool} 的登录文件（只是猜，真机上以能不能跑为准）"}
    return {"code": "ok", "label": STATUS_LABELS["ok"]}


# ---------- 质量统计：从时间线算每个模型的成绩 ----------
def _ts(x):
    import datetime as dt
    try:
        return dt.datetime.fromisoformat(x).timestamp()
    except (TypeError, ValueError):
        return None


def model_stats(records, since=None):
    """records：时间线记录（可多个项目混在一起，带 project 字段更好）。返回 {模型: {build:{…}, verify:{…}}}。
    施工：件数、验收打回率、返工轮数/件、看效果打回率、分钟/件、没有活路次数。验收：验了几次、放行、打回、漏放（放行后老板看效果打回）。"""
    st = {}
    cur = {}           # (项目, 件) → {build: 模型, verify: 模型, verify_passed: 模型}
    disp = {}          # 派工号 → (模型, 岗位, 时间)

    def m(model, role):
        e = st.setdefault(model or "(工具默认)", {"build": {"items": set(), "runs": 0, "reports": 0, "verify_rejects": 0, "verify_passes": 0,
                                                             "reworks": 0, "look_rejects": 0, "look_passes": 0, "minutes": 0.0,
                                                             "no_live": 0, "merged": 0},
                                                   "verify": {"runs": 0, "passes": 0, "rejects": 0, "escaped": 0, "minutes": 0.0}})
        return e[role]
    for r in sorted(records, key=lambda x: _ts(x.get("at")) or 0):
        t = _ts(r.get("at"))
        if since and (t or 0) < since:
            continue
        key = (r.get("project"), r.get("item")); c = cur.setdefault(key, {}); ev = r.get("event")
        if ev == "dispatch" and r.get("role") in ("build", "verify"):
            role = r["role"]; c[role] = r.get("model") or "(工具默认)"
            s = m(c[role], role); s["runs"] += 1
            if role == "build":
                s["items"].add(key)
            if r.get("dispatch"):
                disp[r["dispatch"]] = (c[role], role, t)
        elif ev == "report" and r.get("role") in ("build", "verify"):
            d = disp.get(r.get("dispatch"))
            if d and t and d[2]:
                m(d[0], d[1])["minutes"] += max(0.0, (t - d[2]) / 60)
            if r["role"] == "verify" and c.get("verify"):
                ok = r.get("outcome") == "succeeded"
                v = m(c["verify"], "verify"); v["passes" if ok else "rejects"] += 1
                if ok:
                    c["verify_passed"] = c["verify"]
                if c.get("build"):
                    b = m(c["build"], "build"); b["verify_passes" if ok else "verify_rejects"] += 1
            elif r["role"] == "build" and c.get("build"):
                m(c["build"], "build")["reports"] += 1
        elif ev == "rework" and c.get("build"):
            m(c["build"], "build")["reworks"] += 1
        elif ev in ("gate_reject", "gate_approve") and r.get("kind") == "look" and c.get("build"):
            m(c["build"], "build")["look_rejects" if ev == "gate_reject" else "look_passes"] += 1
            if ev == "gate_reject" and c.get("verify_passed"):
                m(c["verify_passed"], "verify")["escaped"] += 1
        elif ev == "no_live_path" and c.get("build"):
            m(c["build"], "build")["no_live"] += 1
        elif ev == "merge" and c.get("build"):
            m(c["build"], "build")["merged"] += 1
    out = {}
    for model, e in st.items():
        b, v = e["build"], e["verify"]
        n = len(b["items"]); judged = b["verify_rejects"] + b["verify_passes"]; looked = b["look_rejects"] + b["look_passes"]
        out[model] = {
            "build": {"items": n, "runs": b["runs"], "merged": b["merged"],
                      "verify_reject_rate": round(b["verify_rejects"] / judged, 3) if judged else None,
                      "rework_per_item": round(b["reworks"] / n, 2) if n else None,
                      "look_reject_rate": round(b["look_rejects"] / looked, 3) if looked else None,
                      "minutes_per_item": round(b["minutes"] / n, 1) if n else None,
                      "no_live_path": b["no_live"]},
            "verify": {"runs": v["runs"], "passes": v["passes"], "rejects": v["rejects"],
                       "escaped": v["escaped"], "escape_rate": round(v["escaped"] / v["passes"], 3) if v["passes"] else None,
                       "minutes_per_run": round(v["minutes"] / v["runs"], 1) if v["runs"] else None}}
    return out


def _score_build(s):
    return (s.get("verify_reject_rate") or 0) + (s.get("look_reject_rate") or 0) + 0.25 * (s.get("rework_per_item") or 0)


def _pct(x):
    return "—" if x is None else f"{round(x * 100)}%"


def recommend(role, current, stats):
    """一句大白话建议。只建议，绝不自动换主模型。返回 {text, switch_to}。"""
    if role not in ("build", "verify"):
        return {"text": "决策岗不比成绩：用最强的模型。", "switch_to": None}
    cur = current or "(工具默认)"
    mine = (stats.get(cur) or {}).get(role) or {}
    n = mine.get("items", 0) if role == "build" else mine.get("passes", 0) + mine.get("rejects", 0)
    if n < MIN_SAMPLE:
        unit = "件" if role == "build" else "次"
        return {"text": f"{cur} 才{'做' if role == 'build' else '验'}了 {n} {unit}，数据还少，先不下结论（满 {MIN_SAMPLE} {unit}再比）。", "switch_to": None}
    best, best_s = None, None
    for model, e in stats.items():
        o = e.get(role) or {}
        if model == cur:
            continue
        if role == "build":
            if o.get("items", 0) < MIN_SAMPLE:
                continue
            sc = _score_build(o)
            if sc + 0.15 <= _score_build(mine) and (best_s is None or sc < best_s):
                best, best_s = model, sc
        else:
            if o.get("passes", 0) < MIN_SAMPLE or o.get("escape_rate") is None or mine.get("escape_rate") is None:
                continue
            if o["escape_rate"] + 0.15 <= mine["escape_rate"] and (best_s is None or o["escape_rate"] < best_s):
                best, best_s = model, o["escape_rate"]
    if not best:
        return {"text": f"{cur} 目前成绩最好（或差别不大），不用换。", "switch_to": None}
    o = stats[best][role]
    if role == "build":
        txt = (f"建议施工换成 {best}：验收打回 {_pct(o['verify_reject_rate'])} 对 {_pct(mine['verify_reject_rate'])}，"
               f"看效果打回 {_pct(o['look_reject_rate'])} 对 {_pct(mine['look_reject_rate'])}，"
               f"每件返工 {o['rework_per_item']} 对 {mine['rework_per_item']} 轮（{o['items']} 件 对 {mine['items']} 件）。点「换成 {best}」才生效。")
    else:
        txt = (f"建议验收换成 {best}：它放过去又被你看效果打回的只有 {_pct(o['escape_rate'])}，现在的 {cur} 是 {_pct(mine['escape_rate'])}"
               f"（各验了 {o['passes'] + o['rejects']} / {mine['passes'] + mine['rejects']} 次）。点「换成 {best}」才生效。")
    return {"text": txt, "switch_to": best}


def week_usage(records, since):
    """最近 7 天按账号：派工次数、工人分钟数（派工到交卷）。"""
    out, disp = {}, {}
    for r in records:
        t = _ts(r.get("at"))
        if not t or t < since:
            continue
        if r.get("event") in ("dispatch", "restart"):
            acct = r.get("account") or r.get("tool") or "?"
            u = out.setdefault(acct, {"runs": 0, "minutes": 0.0}); u["runs"] += 1
            if r.get("dispatch"):
                disp[r["dispatch"]] = (acct, t)
        elif r.get("event") == "report" and r.get("dispatch") in disp:
            acct, t0 = disp[r["dispatch"]]
            out[acct]["minutes"] = round(out[acct]["minutes"] + max(0.0, (t - t0) / 60), 1)
    return out


# ---------- 首次安装向导 ----------
def propose(h, tools=None):
    """按本机装了什么、magpie 有什么组，给出一套默认岗位卡片。原则：施工、验收不同家；决策用最强；每张卡尽量有个不同账号的备用。"""
    clis = (h or {}).get("clis") or {}
    have = [t for t in KNOWN_TOOLS if (clis.get(t) or {}).get("installed")]
    mg = (h or {}).get("magpie") or {}
    ids = [m["id"] for m in mg.get("models") or []] if mg.get("ok") else []
    groups = [i for i in ids if i.startswith("group/")]
    runner = next((t for t in ("dsh", "pi") if t in have), None)        # 走 magpie 的工具
    cmd = lambda t: ((tools or {}).get(t) or {}).get("cmd") or TOOL_CMDS[t]

    def mag(group):
        return {"tool": runner, "via": "magpie", "cmd": cmd(runner), "models": [group]} if runner and group in groups else None
    cards, notes = {}, []
    b = mag("group/evo-build") or ({"tool": "codex", "via": "cli", "cmd": cmd("codex"), "models": []} if "codex" in have else None)
    v = ({"tool": "claude", "via": "cli", "cmd": cmd("claude"), "models": []} if "claude" in have else mag("group/evo-verify"))
    d = next(({"tool": t, "via": "cli", "cmd": cmd(t), "models": [], "thinking": "high"} for t in ("claude", "codex") if t in have), None)
    if b:
        b.update(thinking=b.get("thinking") or "medium", duty="按任务书写代码和测试，交 JSON 报告")
        fb = mag("group/evo-build") if b["via"] == "cli" else (
            {"tool": "codex", "via": "cli", "cmd": cmd("codex"), "models": []} if "codex" in have else None)
        if fb:
            b["fallback"] = {k: fb[k] for k in ("tool", "via", "cmd", "models")}
        cards["build"] = b
    else:
        notes.append("没找到能施工的工具：装 codex，或装 dsh / pi 并在 magpie 里建 group/evo-build")
    if v:
        v.update(thinking="high", duty="换一个模型从头核对：跑命令、看证据、不过就打回")
        fb = mag("group/evo-verify") if v["via"] == "cli" else None
        if fb:
            v["fallback"] = {k: fb[k] for k in ("tool", "via", "cmd", "models")}
        cards["verify"] = v
    else:
        notes.append("没找到能验收的工具：装 claude，或在 magpie 里建 group/evo-verify")
    if d:
        d["duty"] = "只做技术决定（重试、返工、拆分、问老板）；四类红线回老板"
        cards["decide"] = d
    if not mg.get("ok"):
        notes.append(f"magpie 没响应（{mg.get('url')}）：走 magpie 的卡先不建，开好 magpie 再跑一次向导")
    return {"cards": cards, "notes": notes, "clis": clis, "magpie": {"ok": bool(mg.get("ok")), "models": ids, "groups": groups}}
