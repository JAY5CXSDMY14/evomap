"""功能包 orca-gate-sync：Orca 端闸门结果同步（第十七轮 L-03 + 老板决定①，第十八轮从内核搬出来）。

每轮读到 Orca 闸门列表后（tick.gates）：没经过 evo 就结掉的闸门，「打回 / 不做…」照办（可关），「通过 / 上线…」不执行，
转成「确认…？」等老板在 evo 自己的入口再点。关掉整个功能：Orca 端的结果一律不理（不执行任何东西，最保守），
已经在等确认的闸门照常在 status / App 里显示、照常能确认（那部分是内核状态）。
"""
import evo_time as TM

K = None
CONFIG = {}


def sync_external_gates(s, gates):
    """第十七轮 L-03 + 老板决定①（试运行，orca_gate_sync 默认开）：读 Orca 闸门结果，找出没经过 evo 就结掉的闸门。
    开着：「打回 / 不做 / 不同意 / 再等等 / 拒绝」照办；「通过 / 上线 / 做（老卡的同意 / 继续）」不执行，推一条「确认…？」，
    老板在 evo 自己的入口（Telegram 按钮 / evo approve）再点才生效。关掉：Orca 端的任何结果都要在 evo 入口确认。
    工人也能调 orca 结闸门，所以「放行」类结果永远不直接算数。"""
    on = K.CFG.get("orca_gate_sync", CONFIG.get("execute_negative", True)) is not False   # 项目配置写了以它为准
    seen = s.setdefault("gate_ext_seen", [])
    mine = set(s.get("evo_resolved") or []) | set(s.get("superseded_gates") or {})
    conf = s.setdefault("confirm_gates", {})
    for g in gates or []:
        gid = g.get("id")
        if not gid or g.get("status") in (None, "pending") or gid in mine or gid in seen or gid in conf:
            continue
        k, kind = K.gate_kind(s, gid)
        if not kind:
            continue
        it = s["items"].get(k) if k else None
        if kind == "do" and K.gate_reason(s, gid) != "item":
            it = None                                   # 第二十五轮：转老板 / 外部来报 / 上限卡也是 do 类，但不挂在件的 gates 上
        elif kind in ("look", "do") and (not it or it["state"] in K.QUIET_STATES + ("pushing",)):
            continue
        if kind == "do" and it and it.get("do_ok"):
            continue
        if kind == "look" and K.look_approved(it) and "look_ok" in it:
            continue
        choice = str(g.get("resolution") or g.get("result") or "").strip()
        seen.append(gid); del seen[:-500]
        K.tl(k, "gate_external", kind=kind, gate=gid, choice=choice, executed=bool(on and choice in K.NEG_CHOICES))
        if kind == "look" and it["state"] != "verified":
            # 还没验收通过就被结掉（老板只该看验收过的版本）：重开一个，不算任何结果
            K.new_look_gate(s, k, it, "Orca 端提前结了，重开", "看效果闸门在验收通过前被 Orca 端结掉，已重开")
            K.log(s, f"{k} 看效果闸门在 Orca 端被提前结掉（{choice or '?'}），已重开"); continue
        if on and choice in K.NEG_CHOICES:
            K.mark_evo_resolved(s, gid)
            K.apply_gate(s, gid, choice, "Orca 端" + ("打回" if choice == "打回" else choice) + "，未写原因", source="orca")
            K.notify("gate_external", f"Orca 端点了「{choice}」，已照办", f"{k or gid}", item=k, gate=gid, choice=choice)
            continue
        verb = K.CONFIRM_VERB.get(kind, "通过")
        if kind == "ship":
            who = "、".join(x for x, i in s["items"].items() if i.get("ship_gate") == gid) or gid
        else:
            who = k or gid
        q = f"确认{verb} {who}？（Orca 端点了「{choice or '?'}」，在这里再点一次才生效）"
        conf[gid] = {"kind": kind, "item": k, "choice": choice, "at": TM.now(), "question": q, "options": K.GATE_OPTIONS.get(kind)}
        K.log(s, f"{who} 的{kind}闸门在 Orca 端被点了「{choice}」，没有执行，等老板在 evo 入口确认")
        K.notify("gate_waiting", q, "Orca 端（手机或工人）结的闸门「放行」类结果不直接算数：点下面的按钮确认（Telegram 不方便时 evo approve）。",
               item=k, gate=gid, options=K.GATE_OPTIONS.get(kind), confirm=True)



def apply(ctx):
    global K
    K = ctx.k
    CONFIG.clear(); CONFIG.update(ctx.config)
    ctx.subscribe("tick.gates", lambda ev: sync_external_gates(ev["live"]["s"], ev["live"]["gates"]), priority=10, timeout=300)
