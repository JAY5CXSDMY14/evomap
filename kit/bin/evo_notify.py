"""evo 的提醒通道（可插拔，几个可以同时发）。

每件事先变成一条「事件」（JSON），然后：
  outbox   永远写：~/.evoloop/outbox.jsonl 一行一条，外部 Agent 读这里（见 docs/agent-interface.md）
  webhook  POST 事件 JSON 到配置的 URL，可带 HMAC-SHA256 签名头（给 Muse 或别的 bot 用）
  telegram 只发「要推」的事；闸门消息带「通过 / 打回」按钮，由 evo bot 收按钮
  email    SMTP；Telegram 没配或发失败时兜底，另外收早间汇总
  macos    本机通知（只发要推的事）
  plugin   第十六轮：打开的插件里的 notify_channels（事件 JSON 从 stdin 给插件命令，见 docs/plugins.md）；
           默认只收要推的事（同 telegram，受免打扰），events=all 的渠道每个事件都收

要推的只有：闸门 5 分钟没人处理、件卡住（含状态文件损坏暂停、接棒器心跳停了）、推送连续失败 3 次、岗位因额度暂停、用量异常、上线失败。
其余事件只进 outbox（webhook 设 events=all 时也发）。
免打扰时段（默认 0:00–8:00 上海时间）里要推的事先攒着，到早上 8:30 一次发汇总到 telegram + email。
测试替身：设 EVO_FAKE_NET=<目录> 时不联网，HTTP 请求记到 http.log、邮件记到 mail.log，HTTP 回应取自 http_responses.json。
"""
import fcntl, hashlib, hmac, json, os, smtplib, ssl, subprocess, sys, uuid
import urllib.request
from email.message import EmailMessage

import evo_time as T

SCHEMA_VERSION = 1
PUSH_KINDS = {"gate_waiting", "stalled", "state_corrupt", "push_failed", "rate_limited", "usage_abnormal", "deploy_failed"}
PUSH_KINDS |= {"model_blocked", "magpie_down"}      # 第十四轮：岗位因模型停了、magpie 不通（都要老板动手或知情）
KIND_NAMES = {"gate_waiting": "等你点头", "stalled": "卡住", "state_corrupt": "卡住", "push_failed": "推送失败",
              "rate_limited": "额度暂停", "usage_abnormal": "用量异常", "deploy_failed": "上线失败"}
KIND_NAMES.update({"model_blocked": "岗位停了", "magpie_down": "magpie 不通", "fallback_on": "切到备用"})     # 第十四轮
# 第十七轮：一轮超时、主线本身红、拉 issue 连续失败（含 gh 登录失效）、决策岗连续卡住
PUSH_KINDS |= {"tick_timeout", "main_red", "intake_down", "decider_stuck"}
KIND_NAMES.update({"tick_timeout": "一轮超时", "main_red": "主线红了", "intake_down": "拉不到 issue", "decider_stuck": "决策岗卡住"})
ENV_ALIASES = {"EVO_TG_TOKEN": "TUBU_TG_TOKEN", "EVO_TG_CHAT": "TUBU_TG_CHAT", "TUBU_TG_TOKEN": "EVO_TG_TOKEN",
               "TUBU_TG_CHAT": "EVO_TG_CHAT"}


def env(name, default=None):
    v = os.environ.get(name) if name else None
    if not v and name in ENV_ALIASES:
        v = os.environ.get(ENV_ALIASES[name])
    return v or default


# ---------- 网络（可替身）----------
def _fake_dir():
    return os.environ.get("EVO_FAKE_NET")


def _append(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def http(url, data=None, headers=None, timeout=15, raw=None):
    """发 HTTP。data 是 dict 就发 JSON。返回 (状态码, 解析后的 JSON 或文本)；网络错误返回 (0, 错误文字)。"""
    body = raw if raw is not None else (json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None)
    hd = {"Content-Type": "application/json; charset=utf-8", **(headers or {})} if body is not None else dict(headers or {})
    fd = _fake_dir()
    if fd:
        _append(os.path.join(fd, "http.log"), {"url": url, "headers": hd, "body": body.decode("utf-8") if body else None})
        rp = os.path.join(fd, "http_responses.json")
        with open(rp + ".lock", "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            resp = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
            for key, q in resp.items():
                if key in url and q:
                    r = q.pop(0); json.dump(resp, open(rp, "w", encoding="utf-8"), ensure_ascii=False)
                    return r.get("_status", 200), r
        return 200, {"ok": True, "result": []}
    try:
        req = urllib.request.Request(url, data=body, headers=hd, method="POST" if body is not None else "GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(txt)
            except ValueError:
                return r.status, txt
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            return e.code, str(e)
    except Exception as e:
        return 0, str(e)


def send_mail(subject, text):
    """SMTP 发信，配置全在环境变量：EVO_SMTP_HOST、EVO_SMTP_PORT（默认 465）、EVO_SMTP_USER、EVO_SMTP_PASS、
    EVO_SMTP_TLS（ssl 默认 / starttls / none）、EVO_MAIL_FROM（默认同 USER）、EVO_MAIL_TO（逗号分隔）。没配返回 None。"""
    host, to = env("EVO_SMTP_HOST"), env("EVO_MAIL_TO")
    if not host or not to:
        return None
    frm = env("EVO_MAIL_FROM") or env("EVO_SMTP_USER") or "evo@localhost"
    fd = _fake_dir()
    if fd:
        _append(os.path.join(fd, "mail.log"), {"to": to, "from": frm, "subject": subject, "text": text})
        return True
    msg = EmailMessage(); msg["Subject"] = subject; msg["From"] = frm; msg["To"] = to; msg.set_content(text)
    mode = (env("EVO_SMTP_TLS") or "ssl").lower(); port = int(env("EVO_SMTP_PORT") or (465 if mode == "ssl" else 587))
    try:
        s = smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) if mode == "ssl" else smtplib.SMTP(host, port, timeout=20)
        with s:
            if mode == "starttls":
                s.starttls(context=ssl.create_default_context())
            if env("EVO_SMTP_USER"):
                s.login(env("EVO_SMTP_USER"), env("EVO_SMTP_PASS") or "")
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"邮件没发出去：{e}", file=sys.stderr)
        return False


# ---------- 配置 ----------
class Notifier:
    def __init__(self, cfg, root, project=None):
        self.cfg = cfg or {}
        self.n = self.cfg.get("notify") or {}
        self.root = root
        self.project = project
        self.outbox = os.path.join(root, "outbox.jsonl")
        self.held = os.path.join(root, "held.jsonl")

    # -- 通道配置 --
    def channels(self):
        ch = self.n.get("channels")
        return list(ch) if ch is not None else ["telegram", "email"]

    def tg(self):
        t = self.n.get("telegram") or {}
        # 老配置键（telegram_bot_token_env / telegram_chat_id_env）写了就优先
        tok = env(self.n.get("telegram_bot_token_env") or t.get("token_env") or "EVO_TG_TOKEN")
        chat = env(self.n.get("telegram_chat_id_env") or t.get("chat_env") or "EVO_TG_CHAT")
        owner = env(t.get("owner_user_env") or "EVO_TG_OWNER")
        api = (t.get("api") or env("EVO_TG_API") or "https://api.telegram.org").rstrip("/")
        return tok, chat, owner, api

    def webhooks(self):
        w = self.n.get("webhook") or self.n.get("webhooks") or []
        return [w] if isinstance(w, dict) else list(w)

    def quiet_cfg(self):
        q = self.n.get("quiet_hours", {"start": "00:00", "end": "08:00"})
        if not q:
            return None
        return {"start": q.get("start", "00:00"), "end": q.get("end", "08:00"), "tz": q.get("tz") or self.n.get("tz") or T.DEFAULT_TZ}

    def is_quiet(self, ts=None):
        q = self.quiet_cfg()
        if not q:
            return False
        t = T.local(ts, q["tz"])
        return T.in_range(t.hour * 60 + t.minute, T.hm(q["start"]), T.hm(q["end"]))

    # -- 事件 --
    def event(self, kind, title, body="", item=None, gate=None, data=None, project=None):
        ts = T.now()
        return {"schema_version": SCHEMA_VERSION, "id": uuid.uuid4().hex[:16], "ts": T.iso(ts),
                "epoch": round(ts, 3), "project": project or self.project, "kind": kind,
                "level": "push" if kind in PUSH_KINDS else "info", "title": title, "body": body or "",
                "item": item, "gate": gate, "data": data or {}}

    def emit(self, kind, title, body="", item=None, gate=None, data=None, project=None):
        ev = self.event(kind, title, body, item, gate, data, project)
        _append(self.outbox, ev)                          # 永远写 outbox
        for w in self.webhooks():
            if (w.get("events") or "push") == "all" or ev["level"] == "push":
                self.post_webhook(w, ev)
        if ev["level"] != "push":
            self.plugins(ev, push=False)                  # 第十六轮：events=all 的插件渠道
            return ev
        if self.is_quiet():
            _append(self.held, ev)                        # 免打扰：攒到早上汇总
            return ev
        self.deliver(ev)
        return ev

    def deliver(self, ev):
        """把一条要推的事发到老板那：macOS、Telegram；Telegram 没配/失败 → 邮件兜底（email.mode=always 则都发）。"""
        res = {}
        text = f"{self._prefix(ev)}{ev['title']}\n{ev['body']}".strip()
        if self.n.get("macos") and sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f'display notification {json.dumps(ev["body"] or ev["title"])} with title {json.dumps(ev["title"])}'],
                           capture_output=True)
        ch = self.channels()
        if "telegram" in ch:
            res["telegram"] = self.telegram(text, self._buttons([ev]))
        if "email" in ch:
            mode = (self.n.get("email") or {}).get("mode", "fallback")
            if mode == "always" or not res.get("telegram"):
                res["email"] = send_mail(f"[evo] {ev['title']}", text)
        res.update(self.plugins(ev, push=True))
        return res

    def plugins(self, ev, push):
        """第十六轮：插件通知渠道。插件出什么事都不能拖垮提醒（evo_plugin.invoke 不抛异常，这里再兜一层）。"""
        if os.environ.get("EVO_NO_PLUGINS"):
            return {}
        try:
            import evo_plugin
            return evo_plugin.notify(self.root, ev, push)
        except Exception as e:
            print(f"插件通知渠道出错：{e}", file=sys.stderr)
            return {}

    def _prefix(self, ev):
        return f"[{ev['project']}] " if ev.get("project") else ""

    def _buttons(self, evs):
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

    # -- 通道 --
    def telegram(self, text, buttons=None, chat=None):
        tok, ch, _, api = self.tg()
        chat = chat or ch
        if not tok or not chat:
            return None
        data = {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}
        if buttons:
            data["reply_markup"] = {"inline_keyboard": buttons}
        code, r = http(f"{api}/bot{tok}/sendMessage", data)
        return code == 200 and isinstance(r, dict) and r.get("ok") is not False

    def post_webhook(self, w, ev):
        url = w.get("url") or env(w.get("url_env") or "")
        if not url:
            return None
        body = json.dumps(ev, ensure_ascii=False).encode("utf-8")
        hd = {"X-Evo-Event": ev["kind"], "X-Evo-Schema": str(SCHEMA_VERSION)}
        sec = env(w["secret_env"]) if w.get("secret_env") else None     # 每个 webhook 自己的密钥；没写就不签，不借别人的
        if sec:
            hd["X-Evo-Signature"] = "sha256=" + hmac.new(sec.encode("utf-8"), body, hashlib.sha256).hexdigest()
        code, _ = http(url, raw=body, headers={"Content-Type": "application/json; charset=utf-8", **hd})
        return 200 <= code < 300

    # -- 早间汇总 --
    def digest_due(self):
        if self.is_quiet():
            return False
        q = self.quiet_cfg()
        t = T.local(None, (q or {}).get("tz"))
        return t.hour * 60 + t.minute >= T.hm(self.n.get("digest_at", "08:30"))

    def flush_digest(self, force=False):
        """免打扰期间攒下的要推事项，到点（默认 8:30）合成一条发 telegram + email。返回发出的条数。"""
        if not os.path.exists(self.held) or not (force or self.digest_due()):
            return 0
        with open(self.held + ".lock", "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            if not os.path.exists(self.held):
                return 0
            evs = []
            for l in open(self.held, encoding="utf-8"):
                try:
                    evs.append(json.loads(l))
                except ValueError:
                    pass
            os.remove(self.held)
        if not evs:
            return 0
        seen, uniq = set(), []
        for ev in evs:                                    # 同一件同一类只留最新一条
            k = (ev.get("kind"), ev.get("project"), ev.get("item"), ev.get("gate"))
            if k in seen:
                uniq = [e for e in uniq if (e.get("kind"), e.get("project"), e.get("item"), e.get("gate")) != k]
            seen.add(k); uniq.append(ev)
        lines = [f"夜里攒下 {len(uniq)} 件要你知道的事："]
        for ev in uniq:
            lines.append(f"· [{ev.get('project') or '-'}] {KIND_NAMES.get(ev['kind'], ev['kind'])}：{ev['title']}"
                         + (f" —— {ev['body']}" if ev.get("body") else ""))
        text = "\n".join(lines)
        ch = self.channels()
        if "telegram" in ch:
            self.telegram("☀️ 早间汇总\n" + text, self._buttons(uniq))
        if "email" in ch:
            send_mail(f"[evo] 早间汇总：{len(uniq)} 件", text)
        ev = self.event("digest_morning", "早间汇总", text, data={"count": len(uniq), "events": [e["id"] for e in uniq]}, project="*")
        _append(self.outbox, ev)
        self.plugins(ev, push=True)                       # 插件渠道和 telegram 一样收早间汇总
        for w in self.webhooks():
            if (w.get("events") or "push") == "all":
                self.post_webhook(w, ev)
        return len(uniq)

    def test_all(self):
        """evo notify-test：每个通道各发一条测试消息，返回 {通道: 结果}。不受免打扰限制。"""
        ev = self.event("test", "evo 通知测试", "收到这条说明这个通道通了。", project=self.project or "*")
        out = {"outbox": True}
        _append(self.outbox, ev)
        for i, w in enumerate(self.webhooks()):
            out[f"webhook{i + 1}"] = self.post_webhook(w, ev)
        ch = self.channels()
        if "telegram" in ch:
            out["telegram"] = self.telegram(f"{ev['title']}\n{ev['body']}")
        if "email" in ch:
            out["email"] = send_mail(f"[evo] {ev['title']}", ev["body"])
        out.update(self.plugins(ev, push=True))
        if self.n.get("macos") and sys.platform == "darwin":
            r = subprocess.run(["osascript", "-e", f'display notification "{ev["body"]}" with title "{ev["title"]}"'], capture_output=True)
            out["macos"] = r.returncode == 0
        return out


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
        _, cid, owner, _ = self.N.tg()
        if not cid or str((chat or {}).get("id")) != str(cid):
            return False
        if owner:
            return str((frm or {}).get("id")) == str(owner)
        return (chat or {}).get("type") == "private" and str((frm or {}).get("id")) == str(cid)

    def api(self, method, data):
        tok, _, _, api = self.N.tg()
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
        self.N.telegram(text)
