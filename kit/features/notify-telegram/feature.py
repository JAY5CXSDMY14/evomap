"""功能包 notify-telegram：Telegram 推送渠道 + 按钮机器人 `evo bot`（第十八轮从内核搬出来）。

关掉它：要推的事不再发 Telegram（outbox、邮件兜底、别的渠道照旧），`evo bot` 说「功能关着」。
没有「正在用」的保护：关掉只是不往这里推，配置（EVO_TG_TOKEN 等）留着，不会有东西没人管。
"""
import subprocess
import sys
import time

import evo_tg as TG

K = None


def cmd_bot(a):
    """Telegram 按钮机器人：长轮询 getUpdates，收「通过 / 打回」按钮和打回后的那句原话。只认老板本人。"""
    K.refuse_agents("Telegram 机器人")
    tok, chat, owner, _ = TG.tg_cfg(K.NOTE)
    if not tok or not chat:
        sys.exit("没配 Telegram：设 EVO_TG_TOKEN 和 EVO_TG_CHAT（可选 EVO_TG_OWNER = 你的用户 id）")

    def run_evo(args):
        try:
            r = subprocess.run([sys.executable, K.SELF] + args, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:                # 第十七轮 L-24：不让 bot 进程因为一次超时退出
            return 124, "evo 正忙（3 分钟没回），稍后再点一次"
        return r.returncode, (r.stdout + r.stderr).strip()
    bot = TG.Bot(K.NOTE, run_evo)
    print(f"evo bot 在听（chat {chat}" + (f"，只认用户 {owner}" if owner else "，只认私聊本人") + "）")
    while True:
        n = bot.poll_once(timeout=0 if a.once else 30)
        K.flush_digest()
        K.watchdog_check()
        if a.once:
            return
        if n < 0:
            time.sleep(10)



def _setup_cli(x):
    x.add_argument("--once", action="store_true")


def apply(ctx):
    global K
    K = ctx.k
    ctx.contribute("notify.channel", "10-telegram", TG.Telegram())
    ctx.contribute("cli", "bot", {"help": "Telegram 按钮机器人（长轮询）：只认老板本人；顺带看门狗", "setup": _setup_cli,
                                  "run": cmd_bot, "no_project": True})
