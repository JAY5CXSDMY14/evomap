"""功能包 notify-webhook：webhook 渠道（第十八轮从内核搬出来）。

配置还在全局 config.json 的 notify.webhook / notify.webhooks（{url | url_env, secret_env?, events: push|all}）。
在用的保护：配了 webhook 就算在用（外部 bot 在等它，关掉它们会默默收不到），要关先从配置里删掉。
"""
import hashlib
import hmac
import json

from evo_notify import SCHEMA_VERSION, env, http


def hooks(n):
    w = n.n.get("webhook") or n.n.get("webhooks") or []
    return [w] if isinstance(w, dict) else list(w)


def post(w, ev):
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


class Webhook:
    name = "webhook"

    def on_event(self, n, ev):
        for w in hooks(n):
            if (w.get("events") or "push") == "all" or ev["level"] == "push":
                post(w, ev)

    def test(self, n, ev):
        return {f"webhook{i + 1}": post(w, ev) for i, w in enumerate(hooks(n))}


def in_use(k, config):
    return len(hooks(k.NOTE))


def apply(ctx):
    ctx.contribute("notify.channel", "30-webhook", Webhook())
