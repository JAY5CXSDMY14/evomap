"""evo 内核：提醒（outbox、免打扰攒着、早间汇总、第三方插件渠道）。

第十八轮：Telegram / 邮件 / webhook 三个推送渠道搬成功能包（kit/features/notify-telegram、notify-email、notify-webhook），
走 notify.channel 槽位；这里只留内核那部分（事件格式、outbox、免打扰、汇总的攒和发、macOS 本机通知、第三方插件渠道）。
渠道对象（功能包贡献的）可以有这几个方法，都可选，出错只影响它自己：
  name                      渠道名（telegram / email / webhook…）
  on_event(n, ev)           每个事件都给（免打扰之前；webhook 用）
  push(n, ev, text, res)    要推的事（不在免打扰里）；res 是前面渠道的结果（邮件兜底看 telegram 成没成）；返回 True/False/None
  digest(n, text, evs, ev)  早间汇总
  test(n, ev)               evo notify-test，返回 {名字: True/False/None}

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
import fcntl, json, os, subprocess, sys, uuid
import urllib.request

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


# ---------- 配置 ----------
class Notifier:
    def __init__(self, cfg, root, project=None):
        self.cfg = cfg or {}
        self.n = self.cfg.get("notify") or {}
        self.root = root
        self.project = project
        self.outbox = os.path.join(root, "outbox.jsonl")
        self.held = os.path.join(root, "held.jsonl")
        self.channel_list = lambda: []        # 第十八轮：内核接上功能包的 notify.channel 槽位
        self.hold_ok = lambda: True           # 第十八轮：早报功能（digest）关着时内核设成 False：夜里不攒，直接推

    # -- 通道配置 --
    def channels(self):
        ch = self.n.get("channels")
        return list(ch) if ch is not None else ["telegram", "email"]

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
        self._each("on_event", ev)                        # 第十八轮：webhook 等渠道（功能包）
        if ev["level"] != "push":
            self.plugins(ev, push=False)                  # 第十六轮：events=all 的插件渠道
            return ev
        if self.is_quiet() and self.hold_ok():
            _append(self.held, ev)                        # 免打扰：攒到早上汇总
            return ev
        self.deliver(ev)
        return ev

    def deliver(self, ev):
        """把一条要推的事发到老板那：macOS（内核）、各渠道功能包（按槽位 key 排序：Telegram 先，邮件兜底看它的结果）、第三方插件。"""
        res = {}
        text = f"{self._prefix(ev)}{ev['title']}\n{ev['body']}".strip()
        if self.n.get("macos") and sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f'display notification {json.dumps(ev["body"] or ev["title"])} with title {json.dumps(ev["title"])}'],
                           capture_output=True)
        for ch in self.channel_list():
            if hasattr(ch, "push"):
                try:
                    r = ch.push(self, ev, text, res)
                except Exception as e:
                    print(f"推送渠道 {getattr(ch, 'name', ch)} 出错：{e}", file=sys.stderr)
                    r = False
                if r is not None or getattr(ch, "name", None) not in res:
                    res[getattr(ch, "name", "channel")] = r
        res.update(self.plugins(ev, push=True))
        return res

    def _each(self, method, *args):
        out = {}
        for ch in self.channel_list():
            fn = getattr(ch, method, None)
            if not fn:
                continue
            try:
                r = fn(self, *args)
            except Exception as e:
                print(f"推送渠道 {getattr(ch, 'name', ch)} 出错：{e}", file=sys.stderr)
                r = {getattr(ch, "name", "channel"): False} if method == "test" else None
            if isinstance(r, dict):
                out.update(r)
        return out

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
        ev = self.event("digest_morning", "早间汇总", text, data={"count": len(uniq), "events": [e["id"] for e in uniq]}, project="*")
        self._each("digest", text, uniq, ev)              # Telegram（带按钮）、邮件……（功能包）
        _append(self.outbox, ev)
        self.plugins(ev, push=True)                       # 插件渠道和 telegram 一样收早间汇总
        self._each("on_event", ev)                        # webhook events=all 也收
        return len(uniq)

    def test_all(self):
        """evo notify-test：每个通道各发一条测试消息，返回 {通道: 结果}。不受免打扰限制。"""
        ev = self.event("test", "evo 通知测试", "收到这条说明这个通道通了。", project=self.project or "*")
        out = {"outbox": True}
        _append(self.outbox, ev)
        out.update(self._each("test", ev))                # 各渠道功能包
        out.update(self.plugins(ev, push=True))
        if self.n.get("macos") and sys.platform == "darwin":
            r = subprocess.run(["osascript", "-e", f'display notification "{ev["body"]}" with title "{ev["title"]}"'], capture_output=True)
            out["macos"] = r.returncode == 0
        return out


