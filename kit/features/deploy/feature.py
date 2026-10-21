"""功能包 deploy：上线（第十八轮从内核搬出来）。

- 服务 deploy：老板点了「上线」后跑项目的 deploy_cmd（内核 ship_resolved 调它；成功发 deploy.done，失败 deploy.failed + 推送）。
- 自动收菜：每天 ship_gate_at（默认 08:20）之后第一次有已合并的件，建一个上线闸门（tick.before_save）。
在用：有项目配了 deploy_cmd 就关不掉（关了上线就不部署了，件却会被标成已上线）。
"""
import evo_time as TM

K = None
CONFIG = {}


def auto_ship(s, gates):
    """自动收菜：每天到 ship_gate_at（默认 08:20，晨报前）之后，第一次有已合并的件时：没有等着的上线闸门就建一个。
    一天只建一次（看过就记下当天，老板点「再等等」当天不再建）；auto_ship_gate=false 关掉。"""
    if not K.CFG.get("auto_ship_gate", CONFIG.get("auto_ship_gate", True)):
        return
    now = TM.local(); today = now.strftime("%Y-%m-%d")
    if s.get("auto_ship_day") == today or now.strftime("%H:%M") < K.CFG.get("ship_gate_at", CONFIG.get("ship_gate_at", "08:20")):
        return
    if not any(it["state"] == "merged" for it in s["items"].values()):
        return                                           # 还没有可收菜的：今天的机会留着，等有了再建
    pend = {g["id"] for g in (gates or []) if g.get("status") in (None, "pending")}
    if any(it.get("ship_gate") in pend for it in s["items"].values() if it.get("ship_gate")):
        s["auto_ship_day"] = today
        return K.log(s, "自动收菜：已有等着的上线闸门，不重复建")
    if K.ship_batch(s):                                    # 第十七轮 L-25：主线红没建成不记当天，转绿后当天还能收（主线测试按提交号缓存 30 分钟）
        s["auto_ship_day"] = today
        K.log(s, "自动收菜：已建上线闸门")



class Deploy:
    """服务 deploy。"""

    @staticmethod
    def run(s, batch):
        """跑 deploy_cmd：返回 (ok, 输出尾巴)。没配返回 (True, "")。"""
        dc = K.CFG.get("deploy_cmd")
        if not dc:
            return True, ""
        r = K.run_cmd(dc, cwd=K.CFG["repo"], shell=True, timeout=K.tmo("deploy"))
        tail = (r.stdout + r.stderr)[-300:]
        if r.returncode:
            return False, tail
        K.emit("deploy.done", items=batch)
        return True, tail


def in_use(k, config):
    return sum(1 for code in k.list_projects() if (k._read_json(k._project_cfg_path(code)).get("deploy_cmd") or "").strip())


def apply(ctx):
    global K
    K = ctx.k
    CONFIG.clear(); CONFIG.update(ctx.config)
    ctx.provide("deploy", Deploy)
    ctx.subscribe("tick.before_save", lambda ev: auto_ship(ev["live"]["s"], ev["live"]["gates"]), priority=50, timeout=600)
