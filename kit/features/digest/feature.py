"""功能包 digest：早报和每晚汇总（第十八轮从内核搬出来）。

- 早报（早间汇总）：免打扰时段（默认 0:00–8:00）里要推的事先攒着，到点（notify.digest_at，默认 08:30）合成一条发出去。
  关掉这个功能：夜里也直接推（不攒），也就没有早报。
- 每晚汇总：`evo digest [--post]`，夜审时自动跑一次（今天合并了什么、可收菜、卡住的），可贴到日报 issue、发邮件（服务 mail.send 有就发）。
在用：攒着还没发的早报事项（held.jsonl 不空）时关不掉，免得这些事没人发。
"""
import os

import evo_time as TM

K = None
CONFIG = {}


def cmd_digest(a):
    """每晚汇总：今天合并了什么、什么在等老板、什么卡住了。可贴到 daily-report issue。"""
    s = K.load(); today = TM.local().strftime("%m-%d")
    done = [l for l in s["log"] if l.startswith(today) and ("已合并" in l or "老板" in l)]
    stuck = [f"{k} {it['title']}" for k, it in s["items"].items() if it.get("stalled") or it["state"] in ("escalated", "asking")]
    ready = [f"{k} {it['title']}" for k, it in s["items"].items() if it["state"] == "merged"]
    text = "\n".join(["## 今日动静"] + (done or ["（无）"]) + ["## 可收菜（已合并待上线）"] + (ready or ["（无）"]) +
                     ["## 卡住或交决策岗"] + (stuck or ["（无）"]))
    print(text)
    if a and a.post and K.CFG.get("github_repo") and K.CFG.get("digest_issue"):
        K.gh_run("issue", "comment", str(K.CFG["digest_issue"]), "-R", K.CFG["github_repo"], "-b", text)
    if stuck or ready:
        K.notify("digest_nightly", "今晚汇总", text, ready=len(ready), stuck=len(stuck))
        if K.CFG.get("notify", {}).get("email", {}).get("nightly", CONFIG.get("nightly_email", True)) and "email" in K.NOTE.channels() and K.svc("mail.send"):
            K.svc("mail.send")(f"[evo] {K.CODE} 今晚汇总：可收菜 {len(ready)}，卡住 {len(stuck)}", text)



class Digest:
    """服务 digest。"""

    @staticmethod
    def morning():
        n = K.NOTE.flush_digest()
        if n:
            print(f"早间汇总已发：{n} 件")
        return n

    @staticmethod
    def nightly(post=True):
        import argparse
        cmd_digest(argparse.Namespace(post=post))


def _setup_cli(x):
    x.add_argument("--post", action="store_true")


def in_use(k, config):
    p = k.NOTE.held
    return sum(1 for line in open(p, encoding="utf-8") if line.strip()) if os.path.exists(p) else 0


def apply(ctx):
    global K
    K = ctx.k
    CONFIG.clear(); CONFIG.update(ctx.config)
    ctx.provide("digest", Digest)
    ctx.contribute("cli", "digest", {"help": "每晚汇总（--post 贴到日报 issue）", "setup": _setup_cli, "run": cmd_digest})
