"""功能包 notify-email：邮件渠道（第十八轮从内核搬出来）。

贡献 notify.channel（Telegram 之后，兜底）、服务 mail.send（每晚汇总 evo digest 用）。关掉：不发邮件，别的照旧。
"""
import evo_mail as M


class Email:
    name = "email"

    def __init__(self, cfg):
        self.cfg = cfg

    def _mode(self, n):
        return (n.n.get("email") or {}).get("mode") or self.cfg.get("mode") or "fallback"

    def push(self, n, ev, text, res):
        if "email" not in n.channels():
            return None
        if self._mode(n) == "always" or not res.get("telegram"):
            return M.send_mail(f"[evo] {ev['title']}", text)
        return None

    def digest(self, n, text, evs, ev):
        if "email" in n.channels():
            M.send_mail(f"[evo] 早间汇总：{len(evs)} 件", text)

    def test(self, n, ev):
        if "email" not in n.channels():
            return {}
        return {"email": M.send_mail(f"[evo] {ev['title']}", ev["body"])}


def apply(ctx):
    ctx.provide("mail.send", M.send_mail)
    ctx.contribute("notify.channel", "20-email", Email(ctx.config))
