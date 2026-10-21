#!/usr/bin/env python3
"""example-hello：evo 示例插件（纯 Python 标准库）。

协议（docs/plugins.md）：evo 把请求 JSON 写到 stdin，插件把卡片 JSON 写到 stdout，退出码 0。
  python3 hello.py page     侧栏页「你好」（按钮 → 同一个命令，request.action 带按钮的 action）
  python3 hello.py command  输入框「/hello 参数」（request.args 是参数）
  python3 hello.py notify   通知渠道：request.event 是事件，追加到 $EVO_PLUGIN_DATA/notify.log，不用输出
  python3 hello.py item     件详情页按钮（request.project / request.item）
"""
import datetime, json, os, random, sys

DATA = os.environ.get("EVO_PLUGIN_DATA") or "."


def card(title, blocks, subtitle=None):
    c = {"schema_version": 1, "title": title, "blocks": blocks}
    if subtitle:
        c["subtitle"] = subtitle
    return c


def bump():
    """数一下侧栏页被打开了几次（演示插件自己的数据目录 $EVO_PLUGIN_DATA）。"""
    p = os.path.join(DATA, "visits.txt")
    try:
        n = int(open(p).read().strip() or 0) + 1
    except (OSError, ValueError):
        n = 1
    try:
        open(p, "w").write(str(n))
    except OSError:
        pass
    return n


def page(req):
    act = req.get("action")
    now = datetime.datetime.now().strftime("%H:%M")
    blocks = []
    if act == "roll":
        n = random.randint(1, 6)
        blocks.append({"type": "text", "text": f"🎲 掷出了 {n}", "style": "title", "tone": "accent"})
    elif act == "again":
        blocks.append({"type": "text", "text": "又打了一次招呼 👋", "style": "title", "tone": "success"})
    visits = bump()
    blocks += [
        {"type": "text", "text": f"这页是 example-hello 插件画的：插件只输出一段卡片 JSON，App 用通用渲染器画出来。现在 {now}。"},
        {"type": "list", "items": [
            {"title": "侧栏页", "subtitle": "就是这一页", "symbol": "sidebar.left", "badge": "sidebar_pages"},
            {"title": "输入框命令", "subtitle": "在下面输入框打 /hello 老板", "symbol": "text.cursor", "badge": "composer_commands"},
            {"title": "通知渠道", "subtitle": "要推的事会追加到插件数据目录的 notify.log", "symbol": "bell", "badge": "notify_channels"},
            {"title": "件按钮", "subtitle": "件详情页多一个「跟这件打招呼」", "symbol": "hand.wave", "badge": "item_actions"},
        ]},
        {"type": "table", "columns": ["项", "值"], "rows": [["打开次数", visits], ["插件接口", os.environ.get("EVO_API", "?")],
                                                           ["数据目录", os.path.basename(DATA)]]},
        {"type": "buttons", "buttons": [
            {"label": "再打个招呼", "action": "again", "style": "primary"},
            {"label": "掷骰子", "action": "roll", "payload": {"sides": 6}},
        ]},
        {"type": "text", "text": "按钮点了会再跑一次插件命令（request.action = 按钮的 action）。", "style": "caption"},
    ]
    return card("你好，老板 👋", blocks, subtitle="example-hello 0.1.0")


def command(req):
    who = (req.get("args") or "").strip() or "老板"
    return card(f"你好，{who}！", [
        {"type": "text", "text": f"这是 /hello 的回话：插件收到的参数是「{req.get('args') or ''}」，当前项目 {req.get('project') or '（没选）'}。"},
        {"type": "buttons", "buttons": [{"label": "掷骰子", "action": "roll", "style": "primary"}]},
    ]) if req.get("action") != "roll" else card("🎲 " + str(random.randint(1, 6)), [{"type": "text", "text": "随手掷了一个。"}])


def notify(req):
    ev = req.get("event") or {}
    with open(os.path.join(DATA, "notify.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": ev.get("kind"), "project": ev.get("project"), "title": ev.get("title"), "body": ev.get("body")},
                           ensure_ascii=False) + "\n")
    return None


def item(req):
    return card(f"你好，{req.get('item') or '?'}", [
        {"type": "text", "text": f"项目 {req.get('project') or '?'} 的件 {req.get('item') or '?'}：插件能拿到项目代号和件号，自己去读 evo -p 代号 log 件号 --json。"},
    ])


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "page"
    raw = sys.stdin.read()
    req = json.loads(raw) if raw.strip() else {}
    out = {"page": page, "command": command, "notify": notify, "item": item}[mode](req)
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
