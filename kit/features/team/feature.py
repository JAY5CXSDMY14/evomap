"""功能包 team：团队 / 模型协调（第十四轮的 evo_team，第十八轮从内核搬出来）。

岗位卡片（工具·模型·思考档位·职责·备用）、magpie 健康检查、主模型 / 备用路线、额度满切备用、模型下线或撞模型时停岗、
每个模型的成绩和建议、新模型发现；`evo team`、`evo models`、面板 / App 的团队页。
内核派工只认服务 team（rc / route / has_fallback / block / unblock / fallback_on / fallback_off）；关掉它，派工按
roles 配置的第一个模型走、没有备用、不查 magpie。
第十八轮多机器：magpie 的模型分组可以带机器前缀（machine.yml 的 model_prefix，例 mini/group/evo-build），见 docs/multi-machine.md。
"""
import json
import os
import re
import sys

import evo_notify as NT
import evo_team as TEAM
import evo_time as TM

K = None


MODEL_ROLES = ("build", "verify")


MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")    # 模型名会填进工人命令行（{model}），只许安全字符


def magpie_models(timeout=3):
    """读 magpie 的 GET {magpie_url}/v1/models（OpenAI 格式 {"data":[{"id":…}]}）。读不到返回 None。
    组（例如 group/evo-build）如果带 members / models 列表，就用来查施工、验收有没有重叠。"""
    url = (K.GCFG.get("magpie_url") or K.DEFAULTS["magpie_url"]).rstrip("/") + "/v1/models"
    try:
        code, data = K.magpie_http(url, timeout=timeout)     # 第十八轮：远程 magpie 的分组前缀按本机配置补别名
    except Exception:
        return None
    if code != 200 or not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return None
    return [m for m in data["data"] if isinstance(m, dict) and isinstance(m.get("id"), str)]


def _members(mid, listed):
    """一个模型名展开成实际模型：magpie 列表里这个组带了成员就用成员，否则就是它自己。"""
    e = next((m for m in listed or [] if m["id"] == mid), None) or {}
    mem = e.get("members") or e.get("models")
    return {x for x in mem if isinstance(x, str)} if isinstance(mem, list) and mem else {mid}


def models_warnings(cfg, listed, where="全局"):
    """核对一份配置的施工/验收模型：magpie 列表里没有的、两边重叠的，各出一句警告。"""
    out = []
    roles = cfg.get("roles") or {}
    lists = {r: list((roles.get(r) or {}).get("models") or []) for r in MODEL_ROLES}
    if listed is not None:
        ids = {m["id"] for m in listed}
        for r in MODEL_ROLES:
            out += [f"{where} roles.{r}.models 里的 {m} 不在 magpie /v1/models 里" for m in lists[r] if m not in ids]
    b = set().union(*[_members(m, listed) for m in lists["build"]]) if lists["build"] else set()
    v = set().union(*[_members(m, listed) for m in lists["verify"]]) if lists["verify"] else set()
    if b & v:
        out.append(f"{where} 施工和验收的模型有重叠（{', '.join(sorted(b & v))}）：验收可能和施工用同一个模型")
    return out


def project_model_view(code, listed):
    """一个项目的模型现状：跟随全局时会用什么、覆盖了什么、实际用什么。"""
    raw = K._read_json(K._project_cfg_path(code))
    follow = K.effective_config({k: v for k, v in raw.items() if k != "overrides"})
    eff = K.effective_config(raw)
    ov = ((raw.get("overrides") or {}).get("roles") or {})
    return {"follow": {r: (follow["roles"].get(r) or {}).get("models") or [] for r in MODEL_ROLES},
            "override": {r: (ov.get(r) or {}).get("models") for r in MODEL_ROLES},
            "effective": {r: (eff["roles"].get(r) or {}).get("models") or [] for r in MODEL_ROLES},
            "warnings": models_warnings(eff, listed, code)}


def set_model_override(code, role, model):
    """写项目覆盖 overrides.roles.<岗位>.models=[model]；model 为空就删掉覆盖（回到跟随全局）。原子写。"""
    p = K._project_cfg_path(code)
    c = K._read_json(p)
    ov = c.setdefault("overrides", {}); rs = ov.setdefault("roles", {}); r = rs.setdefault(role, {})
    if model:
        r["models"] = [model]
    else:
        r.pop("models", None)
        if not r:
            rs.pop(role)
        if not rs:
            ov.pop("roles")
        if not ov:
            c.pop("overrides")
    tmp = p + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2); os.replace(tmp, p)


def cmd_models(a):
    """evo models：核对全局和各项目的施工/验收模型（magpie 列表里有没有、两边是否重叠）。
    evo -p AB models set build <模型> / clear build：单项目覆盖（面板下拉框也走这里）。外部 Agent 不能改。"""
    act = a.action or "check"
    if act in ("set", "clear"):
        K.refuse_agents("改模型")
        if not K.HAS_PROJECT:
            sys.exit("改模型要指定项目：evo -p <代号> models set build <模型>")
        if a.role not in MODEL_ROLES:
            sys.exit("岗位只能是 build（施工）或 verify（验收）")
        m = (a.model or "").strip() if act == "set" else ""
        if act == "set" and not MODEL_RE.match(m):
            sys.exit("模型名只能用字母、数字和 . _ : / @ + -（不超过 128 个字符）")
        set_model_override(K.CODE, a.role, m or None)
        print(f"{K.CODE} {'施工' if a.role == 'build' else '验收'}模型：" + (m if m else "跟随全局"))
        for w in project_model_view(K.CODE, magpie_models())["warnings"]:
            print("  ! " + w)
        return
    listed = magpie_models()
    if getattr(a, "json", False):
        doc = {"schema_version": K.APP_SCHEMA_VERSION, "magpie_url": K.GCFG.get("magpie_url"), "magpie_ok": listed is not None,
               "models": [m["id"] for m in listed] if listed is not None else None}
        if K.HAS_PROJECT:
            doc.update(project=K.CODE, **project_model_view(K.CODE, listed))
        print(json.dumps(doc, ensure_ascii=False)); return
    g = K.merge(K.DEFAULTS, K._read_json(K._global_path()))
    warns = []
    if listed is None:
        print(f"  ! magpie 没响应（{g.get('magpie_url')}/v1/models），跳过「模型在不在列表里」的核对")
    else:
        print(f"  ✓ magpie 列出 {len(listed)} 个模型/组")
    warns += models_warnings(g, listed)
    for code in ([K.CODE] if K.HAS_PROJECT else K.list_projects()):
        raw = K._read_json(K._project_cfg_path(code))
        if (raw.get("overrides") or {}).get("roles") or raw.get("roles"):     # 只核对自己改过模型的项目，其余同全局
            warns += project_model_view(code, listed)["warnings"]
    for w in warns:
        print("  ! " + w)
    if not warns:
        print("  ✓ 施工/验收模型都在 magpie 里，且两边不重叠")
    sys.exit(1 if warns else 0)


TEAM_FIELDS = ("tool", "via", "cmd", "models", "thinking", "duty", "fallback", "account")


def team_tools():
    return (K.GCFG.get("tools") or K.global_config().get("tools") or {})


def _uses_magpie():
    for rc in K.team_roles().values():
        rc = rc or {}
        if rc.get("cmd") and (TEAM.via_of(rc) == "magpie" or TEAM.via_of(TEAM.fallback_rc(rc, team_tools()) or {}) == "magpie"):
            return True
    return False


def team_health(force=False):
    """健康表（magpie 模型列表、本机 CLI）：缓存 5 分钟；真刷新那次顺带发 magpie 通断 / 新模型 / 模型下线事件（整机只发一次）。"""
    h, evs = TEAM.health(K.EVO_ROOT, os.path.expanduser("~"), K.GCFG.get("magpie_url"), K.magpie_http, TM.now(), team_tools(), force)
    for kind, data in evs:
        team_event(kind, data)
    return h


def team_event(kind, data):
    if kind == "magpie_down" and _uses_magpie():
        K.notify("magpie_down", "magpie 不通", f"{data['url']} 没响应。走 magpie 的岗位：有备用的切到备用，没有的先停；"
               "工具自带模型的岗位照常跑。正在跑的不打断，magpie 恢复后下一次派工自动接上。", url=data["url"])
    elif kind == "magpie_up":
        K.notify("magpie_up", "magpie 恢复", "走 magpie 的岗位下一次派工起恢复", url=data["url"])
    elif kind == "model_new":
        K.notify("model_new", "新模型可用", "magpie 里新出现：" + "、".join(data["models"]) +
               "。团队页可以挑一个项目、一个岗位试用几件，和现在的比一比再定（evo -p 代号 team trial 岗位 模型）。", models=data["models"])
    elif kind == "model_gone":
        K.notify("model_gone", "模型下线", "magpie 里不见了：" + "、".join(data["models"]) + "。用到它的岗位会停下，等你在团队页换一个。",
               models=data["models"])


def team_rc(role, fallback=False):
    rc = K.team_roles().get(role) or {}
    return (TEAM.fallback_rc(rc, team_tools()) or rc) if fallback else rc


def team_route(role, it=None):
    """这次派工走主模型还是备用：(路线, 原因代号, 说明, 能用的模型)。路线 None = 这个岗位现在不能派。"""
    rc = K.team_roles().get(role) or {}
    e = K._rl_peek().get(role) or {}
    paused = e.get("until", 0) > TM.now()
    fb = TEAM.fallback_rc(rc, team_tools())
    fbp = bool(K.rl_paused(role + ":fallback")) if fb else False
    if fb and paused and e.get("account") and TEAM.account_of(fb) == e["account"]:
        fbp = True                                       # 备用和主模型是同一个订阅：一起满
    return TEAM.route(role, rc, team_health(), TEAM.registry(K.EVO_ROOT), paused, fbp,
                      (it or {}).get("build_model") if role == "verify" else None, team_tools())


def team_has_fallback(role, acct=None):
    fb = TEAM.fallback_rc(K.team_roles().get(role) or {}, team_tools())
    return bool(fb) and (acct is None or TEAM.account_of(fb) != acct)


def team_block(s, k, it, role, code, why):
    """岗位停了（模型下线/不认识、和施工撞模型、magpie 不通且没备用）：件标「等换模型」，同一原因每个项目只推一次。"""
    it["waiting"] = "magpie_down" if code == "magpie_down" else "model_blocked"
    it["model_block"] = why
    tb = s.setdefault("team_blocked", {})
    if tb.get(role) == why:
        return
    tb[role] = why
    name = TEAM.ROLE_NAMES.get(role, role)
    K.log(s, f"{name}岗停了：{why}")
    K.tl(k, "model_blocked", role=role, code=code, why=why)
    if code != "magpie_down":                            # magpie 不通整机推过一次了
        K.notify("model_blocked", f"{name}岗停了：{TEAM.STATUS_LABELS.get(code, code)}",
               f"{why}。在团队页换一个模型，或 evo team set {role} --model <模型>；换了下一次派工就生效。",
               item=k, role=role, code=code)


def team_unblock(s, role):
    tb = s.get("team_blocked") or {}
    if tb.pop(role, None):
        K.log(s, f"{TEAM.ROLE_NAMES.get(role, role)}岗恢复派工")


def team_fallback_on(role, key, until, acct):
    """主模型额度满、备用接上：不推送（不打扰），outbox 记一条；免打扰时段里的进早间汇总。时间线记在触发的那件上。"""
    fb = TEAM.fallback_rc(K.team_roles().get(role) or {}, team_tools()) or {}
    to = f"{fb.get('tool')}" + (f" · {'/'.join(fb.get('models') or [])}" if fb.get("models") else "")
    name = TEAM.ROLE_NAMES.get(role, role)
    if key:
        K.tl(key, "fallback_on", role=role, to=to, until=TM.iso(until), account=acct)
    ev = K.notify("fallback_on", f"{name}岗额度满，已切到备用 {to}",
                f"{acct} 到 {TM.local(until).strftime('%m-%d %H:%M')} 恢复，到点自动切回；正在跑的不打断，下一次派工起用备用。",
                item=key, role=role, to=to, until=TM.iso(until), account=acct)
    try:
        if ev and K.NOTE.is_quiet() and K.NOTE.hold_ok():
            NT._append(K.NOTE.held, ev)                    # 夜里发生的：早间汇总里有一行
    except Exception:
        pass


def team_fallback_off(role, entry):
    if role.endswith(":fallback") or not team_has_fallback(role):
        return
    name = TEAM.ROLE_NAMES.get(role, role)
    if entry.get("item") and entry.get("project") == K.CODE:
        K.tl(entry["item"], "fallback_off", role=role)
    K.notify("fallback_off", f"{name}岗切回主模型", f"{entry.get('account') or ''} 额度已恢复，下一次派工起用回主模型。", role=role)


def team_records(codes=None):
    out = []
    for code in (codes if codes is not None else (K.list_projects() or ([K.CODE] if K.STATE_DIR else []))):
        p = K.tl_path(code) if not K.env("EVO_CONFIG") else K.tl_path()
        if not p or not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            r.setdefault("project", code); out.append(r)
    return out


def _proj_override(code):
    raw = K._read_json(K._project_cfg_path(code)) if code else {}
    ov = ((raw.get("overrides") or {}).get("roles") or {})
    legacy = raw.get("roles") or {}
    return {r: {**(legacy.get(r) or {}), **(ov.get(r) or {})} for r in set(ov) | set(legacy) if (ov.get(r) or legacy.get(r))}


def _card_public(rc):
    rc = rc or {}
    return {"tool": TEAM.tool_of(rc), "via": TEAM.via_of(rc), "models": list(rc.get("models") or []), "thinking": rc.get("thinking"),
            "account": TEAM.account_of(rc)}


def team_doc(force=False):
    """evo team --json：岗位卡片 + 健康 + 每个模型的成绩 + 建议。schema_version 1，只加字段。"""
    h = team_health(force); reg = TEAM.registry(K.EVO_ROOT); now = TM.now(); pe = K._rl_peek(); tools = team_tools()
    roles = K.team_roles()
    recs = team_records()
    stats = TEAM.model_stats(recs, since=now - 30 * 86400)
    week = TEAM.week_usage(recs, now - 7 * 86400)
    ov = _proj_override(K.CODE) if K.HAS_PROJECT else {}
    pstats = TEAM.model_stats(team_records([K.CODE]), since=now - 30 * 86400) if K.HAS_PROJECT else {}
    cards = []
    for role in TEAM.CARD_ROLES:
        rc = roles.get(role) or {}
        fb = TEAM.fallback_rc(rc, tools)
        st = TEAM.health_status(role, rc, h, pe.get(role), now, tools, reg)
        if st.get("until"):
            st["until"] = TM.iso(st["until"])
        sub = "build" if role == "build" else "verify"
        seen = [m for m, e in stats.items() if (e[sub].get("runs") or 0) > 0] if role != "decide" else []
        acct = K.role_account(role) if rc.get("cmd") else None
        card = {"role": role, "name": TEAM.ROLE_NAMES[role], **_card_public(rc), "account": acct,
                "duty": rc.get("duty"), "configured": bool(rc.get("cmd")),
                "fallback": _card_public(fb) if fb else None, "status": st,
                "warnings": TEAM.card_warnings(role, rc, h, reg, tools, roles.get("build") if role == "verify" else None, K.GCFG.get("model_tiers")),
                "stats": {m: stats[m][sub] for m in seen} if role != "decide" else {},
                "recommendation": TEAM.recommend(role, (rc.get("models") or [None])[0], stats),
                "usage_week": week.get(acct) if acct else None}
        if K.HAS_PROJECT:
            o = ov.get(role) or {}
            card["scope"] = "project" if o else "global"
            card["badge"] = "本项目专用" if o else "跟随全局"
            tr = o.get("trial")
            if tr:
                base = (tr.get("base") or [None])[0] or "(工具默认)"
                done = ((pstats.get(tr["model"]) or {}).get(sub) or {})
                card["trial"] = {"model": tr["model"], "base": base, "needed": tr.get("items", 5), "started": tr.get("started"),
                                 "done": done.get("items", 0) if sub == "build" else done.get("runs", 0),
                                 "compare": {"trial": done or None, "base": ((stats.get(base) or {}).get(sub)) or None}}
        cards.append(card)
    mg = h.get("magpie") or {}
    ids = [m["id"] for m in mg.get("models") or []] if mg.get("ok") else None
    doc = {"schema_version": 1, "generated_at": TM.iso(), "project": K.CODE if K.HAS_PROJECT else None,
           "health_at": TM.iso(h["at"]) if h.get("at") else None,
           "magpie": {"ok": bool(mg.get("ok")), "url": mg.get("url"), "models": ids,
                      "groups": [m["id"] for m in mg.get("models") or [] if m["id"].startswith("group/")] if ids is not None else None,
                      "retired": [m["id"] for m in mg.get("models") or [] if m.get("retired")] if ids is not None else None},
           "clis": h.get("clis") or {}, "cards": cards,
           "suggestions": [{"model": x["model"], "at": TM.iso(x["at"])} for x in reg.get("suggestions") or []],
           "usage_week": week, "thinking_levels": list(TEAM.THINKING),
           "projects": [{"code": c, "name": K._read_json(K._project_cfg_path(c)).get("name", c),
                         "overrides": {r: {k: v for k, v in o.items() if k in TEAM_FIELDS + ("trial",)} for r, o in _proj_override(c).items()}}
                        for c in K.list_projects()]}
    return doc


def team_brief(s):
    """status --json 顶层 team（只加字段）：每张卡一行 + magpie 通不通 + 新模型建议数 + 停着的岗位。"""
    try:
        h = team_health(); reg = TEAM.registry(K.EVO_ROOT); pe = K._rl_peek(); now = TM.now()
        cards = []
        for role in TEAM.CARD_ROLES:
            rc = K.team_roles().get(role) or {}
            st = TEAM.health_status(role, rc, h, pe.get(role), now, team_tools(), reg)
            cards.append({"role": role, "name": TEAM.ROLE_NAMES[role], "tool": TEAM.tool_of(rc), "models": list(rc.get("models") or []),
                          "thinking": rc.get("thinking"), "status": st["code"], "label": st["label"],
                          "until": TM.iso(st["until"]) if st.get("until") else None})
        return {"cards": cards, "magpie_ok": bool((h.get("magpie") or {}).get("ok")),
                "suggestions": len(reg.get("suggestions") or []), "blocked": s.get("team_blocked") or {}}
    except Exception as e:                               # 团队信息出错不能拖垮 status
        return {"error": str(e)[:200]}


def team_tick(s):
    """每轮：刷新健康（缓存 5 分钟）；试用满件数时发一条对比（每次试用只发一次）。"""
    team_health()
    ov = _proj_override(K.CODE)
    done = s.setdefault("team_trials", {})
    for role, o in ov.items():
        tr = o.get("trial")
        if not tr or done.get(role) == tr["model"]:
            continue
        sub = "build" if role == "build" else "verify"
        st = TEAM.model_stats(team_records([K.CODE])).get(tr["model"], {}).get(sub) or {}
        n = st.get("items", 0) if sub == "build" else st.get("runs", 0)
        if n >= tr.get("items", 5):
            done[role] = tr["model"]
            base = (tr.get("base") or ["(工具默认)"])[0] or "(工具默认)"
            rec = TEAM.recommend(role, base, TEAM.model_stats(team_records()))
            K.notify("trial_done", f"{TEAM.ROLE_NAMES.get(role, role)}岗试用 {tr['model']} 满 {n} 件",
                   f"团队页有对比。{rec['text']} 留用：evo team set {role} --model {tr['model']} --project {K.CODE}；"
                   f"不用：evo team clear {role} --project {K.CODE}。", role=role, model=tr["model"])


def _team_cfg_target(project):
    if project:
        project = project.upper()
        if project not in K.list_projects() and not K.env("EVO_CONFIG"):
            sys.exit(f"没有项目 {project}")
        return K._project_cfg_path(project), project
    return K._global_path(), None


def _team_write(path, project, role, fn):
    c = K._read_json(path)
    rs = c.setdefault("overrides", {}).setdefault("roles", {}) if project else c.setdefault("roles", {})
    r = rs.setdefault(role, {})
    fn(r)
    if project:
        if not r:
            rs.pop(role)
        if not rs:
            c["overrides"].pop("roles")
        if not c["overrides"]:
            c.pop("overrides")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2); os.replace(tmp, path)


def _team_effective(path, project):
    if project:
        return K.effective_config(K._read_json(path))
    return K.merge(K.DEFAULTS, K._read_json(path))


def team_check_change(role, after_cfg, changed_models):
    """改之前过一遍安全栏：施工≠验收（含组成员）、模型下线/不认识。返回问题列表（空 = 可以改）。"""
    probs = []
    h = team_health(); reg = TEAM.registry(K.EVO_ROOT); tools = team_tools()
    roles = after_cfg.get("roles") or {}
    rc = roles.get(role) or {}
    for m in changed_models:
        p = TEAM.model_problem(m, rc, h, reg, tools)
        if p:
            probs.append(p[1] + "（evo team 看能选的模型）")
    if role in ("build", "verify") and changed_models:
        other = roles.get("verify" if role == "build" else "build") or {}
        mine = set().union(*[TEAM.members(m, h) for m in changed_models])
        theirs = set().union(*[TEAM.members(m, h) for m in other.get("models") or []]) if other.get("models") else set()
        if mine & theirs:
            probs.append(f"施工和验收不能用同一个模型（含 magpie 组成员）：{', '.join(sorted(mine & theirs))}")
    return probs


def cmd_team(a):
    """evo team [--json] [--refresh]：岗位卡片。set / clear / trial / dismiss / init 见 docs/model-coordination.md。"""
    act = a.action or "show"
    if act in ("show", "json"):
        doc = team_doc(force=a.refresh)
        if a.json or act == "json":
            print(json.dumps(doc, ensure_ascii=False)); return
        mg = doc["magpie"]
        print(f"magpie：{'✓ ' + str(len(mg['models'] or [])) + ' 个模型/组' if mg['ok'] else '✗ 不通 ' + str(mg['url'])}")
        for c in doc["cards"]:
            if not c["configured"]:
                print(f"■ {c['name']}：没配置"); continue
            ms = "/".join(c["models"]) or "工具默认模型"
            print(f"■ {c['name']}  {c['tool']} · {ms}" + (f" · 思考 {c['thinking']}" if c.get("thinking") else "")
                  + f"  【{c['status']['label']}{'，' + c['status']['until'] + ' 恢复' if c['status'].get('until') else ''}】"
                  + (f"  {c['badge']}" if c.get("badge") else ""))
            if c.get("duty"):
                print(f"    职责：{c['duty']}")
            if c.get("fallback"):
                f = c["fallback"]; print(f"    备用：{f['tool']} · {'/'.join(f['models']) or '工具默认模型'}")
            for w in c["warnings"]:
                print(f"    ! {w}")
            print(f"    {c['recommendation']['text']}")
            if c.get("usage_week"):
                print(f"    本周（{c['account']}）：{c['usage_week']['runs']} 次 · {int(c['usage_week']['minutes'])} 分钟")
        for sg in doc["suggestions"]:
            print(f"新模型可用：{sg['model']}（evo -p 代号 team trial 岗位 {sg['model']} 试几件）")
        return
    K.refuse_agents("改模型")
    if act == "init":
        h = team_health(force=True)
        prop = TEAM.propose(h, team_tools())
        if a.json and not a.apply:
            print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, **prop}, ensure_ascii=False)); return
        if not a.apply:
            for r, c in prop["cards"].items():
                print(f"{TEAM.ROLE_NAMES[r]}：{c['tool']} · {'/'.join(c['models']) or '工具默认模型'}"
                      + (f"，备用 {c['fallback']['tool']} · {'/'.join(c['fallback']['models']) or '工具默认'}" if c.get("fallback") else ""))
            for n in prop["notes"]:
                print("  ! " + n)
            print("确认就跑：evo team init --apply"); return
        path = K._global_path()
        for r, c in prop["cards"].items():
            _team_write(path, None, r, lambda x, c=c: (x.update({k: v for k, v in c.items() if k in TEAM_FIELDS}),
                                                         None if c.get("fallback") else x.pop("fallback", None)))
        print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, "ok": True, "applied": list(prop["cards"]), "notes": prop["notes"]}, ensure_ascii=False) if a.json
              else f"已写入 {path}：{'、'.join(TEAM.ROLE_NAMES[r] for r in prop['cards'])}。下一次派工生效。")
        return
    if act == "dismiss":
        TEAM.dismiss_suggestion(K.EVO_ROOT, a.role or ""); print("已收起"); return
    role = a.role
    if role not in TEAM.CARD_ROLES:
        sys.exit("岗位只能是 build（施工）、verify（验收）或 decide（决策）")
    path, project = _team_cfg_target(a.project)
    if act == "clear":
        if not project:
            sys.exit("clear 只用于项目：evo team clear <岗位> --project <代号>（回到跟随全局）")
        _team_write(path, project, role, lambda r: r.clear())
        print(f"{project} {TEAM.ROLE_NAMES[role]}：跟随全局"); return
    model = a.model or getattr(a, "set_model", None)
    for nm, v in (("模型", model), ("备用模型", a.fallback_model)):
        if v and not MODEL_RE.match(v):
            sys.exit(f"{nm}名只能用字母、数字和 . _ : / @ + -（不超过 128 个字符）")
    for v in (a.tool, a.fallback_tool):
        if v and not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", v):
            sys.exit("工具名只能是小写字母数字（例如 claude、codex、dsh、pi）")
    if a.thinking and a.thinking not in TEAM.THINKING:
        sys.exit("思考档位只能是 " + " / ".join(TEAM.THINKING))
    if a.duty and len(a.duty) > 80:
        sys.exit("职责一句话，80 字以内")
    if act == "trial":
        if not project or not model:
            sys.exit("试用要指定项目和模型：evo team trial <岗位> <模型> --project <代号> [--items 5]")
        base = (K.effective_config({k: v for k, v in K._read_json(path).items() if k != "overrides"})["roles"].get(role) or {}).get("models") or []
    tools = team_tools()

    def apply(r):
        if a.tool:
            r["tool"] = a.tool
            r["cmd"] = (tools.get(a.tool) or {}).get("cmd") or TEAM.TOOL_CMDS.get(a.tool) or a.tool
            r.setdefault("via", "cli")
        if a.via:
            r["via"] = a.via
        if model:
            r["models"] = [model]; r.pop("trial", None)
        if act == "trial":
            r["trial"] = {"model": model, "base": base, "items": a.items, "started": TM.iso()}
        if a.thinking:
            r["thinking"] = a.thinking
        if a.duty:
            r["duty"] = a.duty
        if a.no_fallback:
            r.pop("fallback", None)
        elif a.fallback_model or a.fallback_tool:
            fb = r.setdefault("fallback", {})
            if a.fallback_tool:
                fb["tool"] = a.fallback_tool
                fb["cmd"] = (tools.get(a.fallback_tool) or {}).get("cmd") or TEAM.TOOL_CMDS.get(a.fallback_tool) or a.fallback_tool
            if a.fallback_model:
                fb["models"] = [a.fallback_model]
                if a.fallback_model.startswith("group/"):
                    fb.setdefault("via", "magpie")
    # 先在副本上改，过安全栏，再落盘
    trial_cfg = K._read_json(path)
    tmp_rs = (trial_cfg.setdefault("overrides", {}).setdefault("roles", {}) if project else trial_cfg.setdefault("roles", {}))
    apply(tmp_rs.setdefault(role, {}))
    after = K.effective_config(trial_cfg) if project else K.merge(K.DEFAULTS, trial_cfg)
    probs = team_check_change(role, after, [model] if model else [])
    if a.fallback_model:
        fbrc = TEAM.fallback_rc((after.get("roles") or {}).get(role) or {}, tools) or {}
        p = TEAM.model_problem(a.fallback_model, fbrc, team_health(), TEAM.registry(K.EVO_ROOT), tools)
        if p:
            probs.append("备用：" + p[1])
    if probs:
        sys.exit("没改：" + "；".join(probs))
    if not (a.tool or a.via or model or a.thinking or a.duty or a.no_fallback or a.fallback_model or a.fallback_tool):
        sys.exit("要改什么？--model / --thinking / --tool / --duty / --fallback-model / --fallback-tool / --no-fallback")
    _team_write(path, project, role, apply)
    rc = (after.get("roles") or {}).get(role) or {}
    where = f"{project} 本项目专用" if project else "全局"
    print(f"{TEAM.ROLE_NAMES[role]}（{where}）：{TEAM.tool_of(rc)} · {'/'.join(rc.get('models') or []) or '工具默认模型'}"
          + (f" · 思考 {rc['thinking']}" if rc.get("thinking") else "")
          + (f"（试用 {a.items} 件后给你对比）" if act == "trial" else "") + "。下一次派工生效，正在跑的不打断。")


def team_panel_get(full_path, run):
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(full_path).query)
    code = (q.get("code") or [""])[0].upper()
    args = (["-p", code] if code in K.list_projects() else []) + ["team", "--json"] + (["--refresh"] if q.get("refresh") else [])
    rc, o, e = run(*args)
    return (200, o) if rc == 0 else (500, json.dumps({"error": e[-200:]}, ensure_ascii=False))


def team_panel_post(body, run):
    """POST /api/team {action: set|clear|trial|dismiss|init, role, model, thinking, tool, fallback_model, fallback_tool, no_fallback, duty, project, items}。
    真正改配置的是子命令（里面拒绝外部 Agent、校验名字、过安全栏）。"""
    act = str(body.get("action") or "set")
    if act not in ("set", "clear", "trial", "dismiss", "init"):
        return {"ok": False, "error": "action 只能是 set / clear / trial / dismiss / init"}
    args = ["team", act]
    if act == "init":
        args += ["--apply", "--json"]
    elif act == "dismiss":
        args.append(str(body.get("model") or ""))
    else:
        args.append(str(body.get("role") or ""))
        if act == "trial":
            args.append(str(body.get("model") or ""))
        for k, flag in (("model", "--model"), ("thinking", "--thinking"), ("tool", "--tool"), ("duty", "--duty"),
                        ("fallback_model", "--fallback-model"), ("fallback_tool", "--fallback-tool"), ("project", "--project"),
                        ("items", "--items")):
            if body.get(k) not in (None, "") and not (act == "trial" and k == "model"):
                args += [flag, str(body[k])]
        if body.get("no_fallback"):
            args.append("--no-fallback")
    rc, o, e = run(*args)
    return {"ok": rc == 0, "error": None if rc == 0 else (e or o)[-300:], "message": o.strip()[-300:]}



class Team:
    """服务 team。"""
    rc = staticmethod(team_rc)
    route = staticmethod(team_route)
    has_fallback = staticmethod(team_has_fallback)
    block = staticmethod(team_block)
    unblock = staticmethod(team_unblock)
    fallback_on = staticmethod(team_fallback_on)
    fallback_off = staticmethod(team_fallback_off)
    panel_get = staticmethod(team_panel_get)
    panel_post = staticmethod(team_panel_post)
    models = staticmethod(magpie_models)


def _status(s, doc):
    doc["team"] = team_brief(s)


def _setup_team(x):
    x.add_argument("action", nargs="?", choices=["show", "set", "clear", "trial", "dismiss", "init"]); x.add_argument("role", nargs="?")
    x.add_argument("model", nargs="?"); x.add_argument("--json", action="store_true"); x.add_argument("--refresh", action="store_true")
    x.add_argument("--model", dest="set_model"); x.add_argument("--thinking"); x.add_argument("--tool"); x.add_argument("--via", choices=["magpie", "cli"])
    x.add_argument("--duty"); x.add_argument("--fallback-model"); x.add_argument("--fallback-tool"); x.add_argument("--no-fallback", action="store_true")
    x.add_argument("--project"); x.add_argument("--items", type=int, default=5); x.add_argument("--apply", action="store_true")


def _setup_models(x):
    x.add_argument("action", nargs="?", choices=["check", "set", "clear"]); x.add_argument("role", nargs="?"); x.add_argument("model", nargs="?")
    x.add_argument("--json", action="store_true")


def apply(ctx):
    global K
    K = ctx.k
    ctx.provide("team", Team)
    ctx.contribute("status", "team", _status)
    ctx.contribute("page", "team", {"title": "团队", "icon": "person.3"})
    ctx.contribute("cli", "team", {"help": "岗位卡片；set / clear / trial / dismiss / init", "setup": _setup_team,
                                   "run": cmd_team, "no_project": True})
    ctx.contribute("cli", "models", {"help": "核对施工/验收模型；-p 代号 models set|clear build|verify [模型] 改单项目覆盖",
                                     "setup": _setup_models, "run": cmd_models, "no_project": True})
    ctx.subscribe("tick.after_dispatch", lambda ev: team_tick(ev["live"]["s"]), priority=40, timeout=300)
