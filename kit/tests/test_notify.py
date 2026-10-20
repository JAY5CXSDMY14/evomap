"""提醒通道：outbox 永远写、只推五类事、免打扰攒到早间汇总、闸门 5 分钟带按钮、webhook 签名、邮件兜底、Telegram 机器人只认老板。"""
import hashlib, hmac, json, os

from conftest import state_is

NOON = "2026-10-20T12:00:00+08:00"


def stall(loop, code="AB"):
    """让一件「疑似卡住」：工人进程不在了（要推的事）。"""
    loop.env["FAKE_WORKER_STATUS"] = "dead"
    loop.tick(code)
    loop.env.pop("FAKE_WORKER_STATUS")


def mail_env(loop):
    loop.env.update(EVO_SMTP_HOST="smtp.fake", EVO_MAIL_TO="boss@example.com")


def test_outbox_gets_every_event_but_only_push_kinds_are_pushed(loop):
    loop.project("AB")
    loop.plan(verify=["fail", "fail", "fail"])
    loop.add("AB")
    loop.run_until("AB", state_is("escalated"), n=12)
    ev = loop.outbox()
    assert ev and all(e["schema_version"] == 1 and e["project"] == "AB" for e in ev)
    esc = [e for e in ev if e["kind"] == "escalated"]
    assert esc and esc[0]["level"] == "info" and esc[0]["item"] == "AB-FIX-001"
    assert esc[0]["ts"].startswith("2026-10-20T12:00:00+08:00")
    assert loop.telegram_sent() == []                   # 交决策岗不推老板（交给决策岗）
    stall(loop)
    loop.add("AB", "修复设置页保存失败", "api/")
    stall(loop)
    sent = loop.telegram_sent()
    assert len(sent) == 1 and "疑似卡住" in sent[0]["text"] and sent[0]["text"].startswith("[AB]")
    assert [e for e in loop.outbox() if e["kind"] == "stalled"][0]["level"] == "push"


def test_email_is_fallback_when_telegram_missing_or_failing(loop):
    mail_env(loop)
    loop.project("AB")
    loop.add("AB")
    stall(loop)                                          # Telegram 正常：不发邮件
    assert len(loop.telegram_sent()) == 1 and loop.mails() == []
    loop.http_responses({"sendMessage": [{"_status": 500, "ok": False}]})
    loop.add("AB", "修复设置页保存失败", "api/")
    stall(loop)                                          # Telegram 第一条失败：那条走邮件兜底
    m = loop.mails()
    assert len(m) == 1 and "疑似卡住" in m[0]["subject"] and m[0]["to"] == "boss@example.com"
    for k in ("EVO_TG_TOKEN", "EVO_TG_CHAT"):
        loop.env.pop(k)
    n_tg = len(loop.telegram_sent())
    loop.add("AB", "修复首页加载很慢", "home/")
    stall(loop)                                          # 没配 Telegram：邮件
    assert any("首页" in x["text"] for x in loop.mails()) and len(loop.telegram_sent()) == n_tg


def test_quiet_hours_hold_until_morning_digest(loop):
    mail_env(loop)
    loop.project("AB")
    loop.add("AB")
    loop.env["EVO_NOW"] = "2026-10-21T02:00:00+08:00"
    stall(loop)
    assert loop.telegram_sent() == [] and loop.mails() == []
    assert [e["kind"] for e in loop.outbox()] == ["stalled"]          # outbox 照写
    held = os.path.join(loop.root, "held.jsonl")
    assert os.path.exists(held)
    loop.env["EVO_NOW"] = "2026-10-21T08:10:00+08:00"                # 过了免打扰，但没到 8:30
    loop.tick("AB"); loop.ok("-p", "AB", "once")
    assert loop.telegram_sent() == []
    loop.env["EVO_NOW"] = "2026-10-21T08:31:00+08:00"
    loop.ok("-p", "AB", "once")
    sent = loop.telegram_sent()
    assert len(sent) == 1 and "早间汇总" in sent[0]["text"] and "卡住" in sent[0]["text"]
    assert len(loop.mails()) == 1 and "早间汇总" in loop.mails()[0]["subject"]
    assert not os.path.exists(held)
    loop.ok("-p", "AB", "once")                                       # 只发一次
    assert len(loop.telegram_sent()) == 1
    assert any(e["kind"] == "digest_morning" for e in loop.outbox())


def test_quiet_hours_and_digest_time_are_configurable(loop):
    loop.write_global({"notify": {"macos": False, "quiet_hours": {"start": "11:00", "end": "13:00"}, "digest_at": "13:15"}})
    loop.project("AB")
    loop.add("AB")
    stall(loop)                                                       # 12:00 在自定义免打扰里
    assert loop.telegram_sent() == []
    loop.env["EVO_NOW"] = "2026-10-20T13:05:00+08:00"
    loop.ok("-p", "AB", "once")
    assert loop.telegram_sent() == []
    loop.env["EVO_NOW"] = "2026-10-20T13:20:00+08:00"
    loop.ok("-p", "AB", "once")
    assert "早间汇总" in loop.telegram_sent()[0]["text"]


def test_gate_unhandled_5_minutes_pushes_once_with_buttons(loop):
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))
    loop.tick("AB")
    assert loop.telegram_sent() == []                                 # 看效果闸门从验收通过才计时
    loop.env["EVO_NOW"] = "2026-10-20T12:06:00+08:00"
    loop.tick("AB")
    sent = loop.telegram_sent()
    assert len(sent) == 1 and "看效果" in sent[0]["text"]
    gate = loop.status_json("AB")["gates"][0]["id"]
    kb = sent[0]["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in kb] == ["通过", "打回"]
    assert [b["callback_data"] for b in kb] == [f"g|AB|{gate}|0", f"g|AB|{gate}|1"]
    loop.env["EVO_NOW"] = "2026-10-20T12:20:00+08:00"
    loop.tick("AB")
    assert len(loop.telegram_sent()) == 1


def test_product_gate_counts_from_creation(loop):
    loop.project("AB")
    loop.add("AB", "新增导出订单功能", "api/", ["--product"])
    loop.tick("AB")
    loop.env["EVO_NOW"] = "2026-10-20T12:05:00+08:00"
    loop.tick("AB")
    sent = loop.telegram_sent()
    assert len(sent) == 1 and "做不做" in sent[0]["text"]
    assert [b["text"] for b in sent[0]["reply_markup"]["inline_keyboard"][0]] == ["做", "不做"]


def test_webhook_posts_signed_json(loop):
    loop.env["EVO_WEBHOOK_SECRET"] = "s3cret"
    loop.write_global({"notify": {"macos": False, "channels": ["webhook"],
                                  "webhook": [{"url": "https://muse.test/hook", "secret_env": "EVO_WEBHOOK_SECRET"},
                                              {"url": "https://all.test/hook", "events": "all"}]}})
    loop.project("AB")
    loop.plan(verify=["fail", "fail", "fail"])
    loop.add("AB")
    loop.run_until("AB", state_is("escalated"), n=12)
    loop.add("AB", "修复设置页保存失败", "api/")
    stall(loop)
    reqs = loop.http_log()
    muse = [r for r in reqs if r["url"] == "https://muse.test/hook"]
    assert len(muse) == 1                                             # events 默认 push：只有卡住
    body = muse[0]["body"].encode("utf-8")
    ev = json.loads(body)
    assert ev["kind"] == "stalled" and ev["schema_version"] == 1
    assert muse[0]["headers"]["X-Evo-Event"] == "stalled"
    assert muse[0]["headers"]["X-Evo-Signature"] == "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    allh = [r for r in reqs if r["url"] == "https://all.test/hook"]
    assert {json.loads(r["body"])["kind"] for r in allh} >= {"escalated", "stalled"}
    assert "X-Evo-Signature" not in allh[0]["headers"]
    assert loop.telegram_sent() == []                                 # channels 里没写 telegram


def test_notify_test_hits_every_channel(loop):
    mail_env(loop)
    loop.write_global({"notify": {"macos": False, "channels": ["telegram", "email", "webhook"],
                                  "email": {"mode": "always"}, "webhook": {"url": "https://muse.test/hook"}}})
    loop.project("AB")
    r = loop.ok("notify-test")
    for ch in ("telegram", "email", "webhook1", "outbox"):
        assert ch in r.stdout and "✓" in r.stdout
    assert len(loop.telegram_sent()) == 1 and len(loop.mails()) == 1
    assert any(x["url"] == "https://muse.test/hook" for x in loop.http_log())
    assert loop.outbox()[-1]["kind"] == "test"


# ---------- Telegram 机器人 ----------
def cb(uid, chat, data, n):
    return {"update_id": n, "callback_query": {"id": f"q{n}", "from": {"id": uid}, "data": data,
                                               "message": {"chat": {"id": chat, "type": "private" if uid == chat else "group"}}}}


def msg(uid, chat, text, n):
    return {"update_id": n, "message": {"from": {"id": uid}, "chat": {"id": chat, "type": "private" if uid == chat else "group"},
                                        "text": text}}


def test_bot_reject_with_verbatim_words_only_from_owner(loop):
    loop.env.update(EVO_TG_CHAT="-100", EVO_TG_OWNER="42")             # 群里，只认用户 42
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))
    gate = loop.status_json("AB")["gates"][0]["id"]
    loop.http_responses({"getUpdates": [{"ok": True, "result": [
        cb(99, -100, f"g|AB|{gate}|1", 1),            # 陌生人点打回：忽略
        msg(99, -100, "随便改改", 2),                    # 陌生人发话：忽略
        cb(42, -100, f"g|AB|{gate}|1", 3),            # 老板点打回 → 问原话
        msg(42, -100, "按钮颜色太刺眼", 4),               # 老板的原话
        cb(42, 555, f"g|AB|{gate}|0", 5),             # 别的聊天里点：忽略
    ]}]})
    loop.ok("bot", "--once")
    it = loop.item("AB")
    assert it["state"] == "queued" and it["round"] == 1
    assert "老板看效果打回：按钮颜色太刺眼" in loop.orca_state()["tasks"][it["build"]]["spec"]
    assert "随便改改" not in json.dumps(loop.state("AB"), ensure_ascii=False)
    assert len([e for e in loop.outbox() if e["kind"] == "bot_rejected"]) == 3
    texts = [m["text"] for m in loop.telegram_sent()]
    assert any("请直接回一句原因" in t for t in texts) and any("已打回" in t for t in texts)
    assert json.load(open(os.path.join(loop.root, "bot.json")))["offset"] == 6


def test_bot_approve_button_private_chat_without_owner_id(loop):
    loop.env.update(EVO_TG_CHAT="42")                                 # 没配 EVO_TG_OWNER：只认私聊本人
    loop.project("AB")
    loop.add("AB", "改版注册页按钮", "web/", ["--look"])
    loop.run_until("AB", state_is("verified"))
    gate = loop.status_json("AB")["gates"][0]["id"]
    loop.http_responses({"getUpdates": [{"ok": True, "result": [cb(42, 42, f"g|AB|{gate}|0", 7)]}]})
    loop.ok("bot", "--once")
    assert loop.status_json("AB")["gates"] == []
    st = loop.run_until("AB", state_is("merged"))
    assert st["items"]["AB-FIX-001"]["pushed"] == loop.remote_head("AB")
