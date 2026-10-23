"""Telegram 渠道 + 按钮机器人（第十八轮从内核 evo_notify 搬出来，属于功能包 notify-telegram）。"""
import json, os

import evo_time as T
from evo_notify import env, http


def tg_cfg(n):
    """(token, chat, owner, api)。n 是内核的 Notifier（读 notify 配置）。"""
    nn = n.n
    t = nn.get("telegram") or {}
    # 老配置键（telegram_bot_token_env / telegram_chat_id_env）写了就优先
    tok = env(nn.get("telegram_bot_token_env") or t.get("token_env") or "EVO_TG_TOKEN")
    chat = env(nn.get("telegram_chat_id_env") or t.get("chat_env") or "EVO_TG_CHAT")
    owner = env(t.get("owner_user_env") or "EVO_TG_OWNER")
    api = (t.get("api") or env("EVO_TG_API") or "https://api.telegram.org").rstrip("/")
    return tok, chat, owner, api


def send(n, text, buttons=None, chat=None):
    tok, ch, _, api = tg_cfg(n)
    chat = chat or ch
    if not tok or not chat:
        return None
    data = {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}
    if buttons:
        data["reply_markup"] = {"inline_keyboard": buttons}
    code, r = http(f"{api}/bot{tok}/sendMessage", data)
    return code == 200 and isinstance(r, dict) and r.get("ok") is not False


def buttons(evs):
    """闸门消息带按钮：callback_data = g|<项目>|<闸门>|<选项序号>（≤64 字节）。"""
    rows = []
    for ev in evs:
        if ev.get("kind") != "gate_waiting" or not ev.get("gate") or not ev.get("project"):
            continue
        opts = (ev.get("data") or {}).get("options") or ["通过", "打回"]
        row = []
        for i, o in enumerate(opts[:3]):
            cb = f"g|{ev['project']}|{ev['gate']}|{i}"
            if len(cb.encode()) <= 64:
                row.append({"text": (f"{ev.get('item') or ''} " if len(evs) > 1 else "") + o, "callback_data": cb})
        if row:
            rows.append(row)
    return rows or None


class Telegram:
    """notify.channel 槽位上的渠道对象。"""
    name = "telegram"

    def ready(self, n):
        """第二十五轮（#12）：Telegram 能不能当批卡入口（channels 里有它、token 和 chat 都配了）。"""
        tok, chat, _, _ = tg_cfg(n)
        return "telegram" in n.channels() and bool(tok and chat)

    def push(self, n, ev, text, res):
        if "telegram" not in n.channels():
            return None
        return send(n, text, buttons([ev]))

    def digest(self, n, text, evs, ev):
        if "telegram" in n.channels():
            send(n, "☀️ 早间汇总\n" + text, buttons(evs))

    def test(self, n, ev):
        if "telegram" not in n.channels():
            return {}
        return {"telegram": send(n, f"{ev['title']}\n{ev['body']}")}


# ---------- Telegram 按钮机器人（evo bot）----------
class Bot:
    """长轮询 getUpdates。只认配置的老板：chat_id 必须等于 EVO_TG_CHAT；
    配了 EVO_TG_OWNER（用户 id）时发消息/点按钮的人必须是他；没配时只认私聊且发信人 id == chat_id。其他人一律忽略。"""

    def __init__(self, notifier, run_evo):
        self.N = notifier
        self.run_evo = run_evo                # run_evo(args) -> (rc, out)
        self.state_path = os.path.join(notifier.root, "bot.json")
        self.st = json.load(open(self.state_path, encoding="utf-8")) if os.path.exists(self.state_path) else {"offset": 0, "await": None}

    def save(self):
        tmp = self.state_path + ".tmp"
        json.dump(self.st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, self.state_path)

    def allowed(self, frm, chat):
        _, cid, owner, _ = tg_cfg(self.N)
        if not cid or str((chat or {}).get("id")) != str(cid):
            return False
        if owner:
            return str((frm or {}).get("id")) == str(owner)
        return (chat or {}).get("type") == "private" and str((frm or {}).get("id")) == str(cid)

    def api(self, method, data):
        tok, _, _, api = tg_cfg(self.N)
        return http(f"{api}/bot{tok}/{method}", data, timeout=60)

    def poll_once(self, timeout=30):
        code, r = self.api("getUpdates", {"offset": self.st.get("offset", 0), "timeout": timeout,
                                          "allowed_updates": ["message", "callback_query"]})
        if code != 200 or not isinstance(r, dict):
            return -1
        ups = r.get("result") or []
        for u in ups:
            self.st["offset"] = max(self.st.get("offset", 0), int(u.get("update_id", 0)) + 1)
            try:
                self.handle(u)
            finally:
                self.save()
        return len(ups)

    def handle(self, u):
        if u.get("callback_query"):
            q = u["callback_query"]; msg = q.get("message") or {}
            if not self.allowed(q.get("from"), msg.get("chat")):
                self.N.emit("bot_rejected", "Telegram：陌生人点按钮，已忽略", data={"from": (q.get("from") or {}).get("id")}, project="*")
                return
            self.api("answerCallbackQuery", {"callback_query_id": q.get("id")})
            parts = (q.get("data") or "").split("|")
            if len(parts) != 4 or parts[0] != "g":
                return
            _, code, gate, idx = parts
            opts = self.gate_options(code, gate)
            if opts is None:
                return self.say(f"{code} 的闸门 {gate} 已经处理过或不存在。")
            choice = opts[int(idx)] if idx.isdigit() and int(idx) < len(opts) else None
            if not choice:
                return
            if choice == "打回":
                self.st["await"] = {"code": code, "gate": gate, "since": T.now()}
                return self.say(f"要打回 {code} 的这件：请直接回一句原因（原话会写进返工说明）。回「跳过」就不写原因。")
            self.approve(code, gate, choice)
        elif u.get("message"):
            m = u["message"]
            if not self.allowed(m.get("from"), m.get("chat")):
                self.N.emit("bot_rejected", "Telegram：陌生人发消息，已忽略", data={"from": (m.get("from") or {}).get("id")}, project="*")
                return
            text = (m.get("text") or "").strip()
            aw = self.st.get("await")
            if text in ("/status", "状态"):
                rc, out = self.run_evo(["status"])
                return self.say(out[-3500:] or "（空）")
            if aw and text and T.now() - float(aw.get("since") or 0) > 600:
                self.st["await"] = None                  # 第十七轮 L-24：等原话超过 10 分钟作废，免得随手一句话被当成打回原话
                return self.say(f"刚才那次打回（{aw.get('code')} 的 {aw.get('gate')}）等原话超过 10 分钟，已作废；要打回请再点一次按钮。")
            if aw and text:
                self.st["await"] = None
                words = None if text in ("跳过", "/skip") else text
                return self.approve(aw["code"], aw["gate"], "打回", words)

    def gate_options(self, code, gate):
        rc, out = self.run_evo(["-p", code, "status", "--json"])
        try:
            j = json.loads(out)
        except ValueError:
            return None
        g = next((g for g in j.get("gates", []) if g["id"] == gate), None)
        return (g.get("options") or ["通过", "打回"]) if g else None

    def approve(self, code, gate, choice, words=None):
        rc, out = self.run_evo(["-p", code, "approve", gate, choice] + ([words] if words else []))
        self.say(f"已{choice}：{code} {gate}" + (f"（原话：{words}）" if words else "") if rc == 0 else f"没成功：{out[-300:]}")

    def say(self, text):
        send(self.N, text)
