"""功能包 plugins：第三方插件宿主（第十六轮的外部插件，第十八轮挂到功能包运行时上，作为「第三方」层）。

两层：
  内置功能包  kit/features/<id>/     evo 自带，Python，在进程里跑，经服务 / 槽位 / 事件和内核说话
  第三方插件  ~/.evoloop/plugins/<名>/  任何语言，一次性子进程，JSON over stdio（docs/plugins.md，接口 evo_api 1.0、卡片 schema_version 1 不变）
这个功能包就是第三方层的开关：开着 = `evo plugin …` 能用、打开的插件收通知、App 显示插件页；关掉 = 第三方插件全部不跑（文件不动）。
在用：有打开的第三方插件时关不掉（先在 App 设置或 evo plugin disable 里关掉它们）。
"""
import json
import os
import sys

import evo_plugin as PLUG

K = None


def cmd_plugin(a):
    """evo plugin …（第十六轮）。插件见 docs/plugins.md；输出格式见 docs/app-contract.md。"""
    act = a.action
    if act == "list":
        doc = PLUG.list_doc(K.EVO_ROOT)
        if a.json:
            print(json.dumps(doc, ensure_ascii=False)); return 0
        if not doc["plugins"]:
            print(f"没有插件（{doc['plugins_dir']}）。装示例：evo plugin install {os.path.join(K.KIT, 'plugins', 'example-hello')}"); return 0
        for p in doc["plugins"]:
            st = "开" if p["active"] else ("关" if p["valid"] and p["compatible"] else "坏")
            c = p["contributes"]
            what = "、".join(f"{n} {len(c[k])}" for k, n in (("sidebar_pages", "侧栏页"), ("composer_commands", "输入框命令"),
                                                             ("notify_channels", "通知渠道"), ("item_actions", "件按钮")) if c[k])
            print(f"[{st}] {p['name']} {p['version'] or ''}  {p['description'] or ''}  （{what or '没有贡献点'}）")
            for e in p["errors"]:
                print("    ! " + e)
            if p["valid"] and not p["compatible"]:
                print(f"    ! evo_api「{p['evo_api']}」和这版 evo（{doc['evo_api']}）不兼容")
        return 0
    if act in ("enable", "disable", "install"):
        K.refuse_agents("开关、安装插件")
        if not a.target:
            sys.exit(f"要写插件名：evo plugin {act} <名字>" if act != "install" else "要写插件文件夹：evo plugin install <目录>")
        try:
            if act == "install":
                info = PLUG.install(K.EVO_ROOT, a.target, force=a.force)
                print(f"已装 {info['name']} → {info['dir']}（默认关着：evo plugin enable {info['name']} 或在 App 设置里打开）")
                for e in info["errors"]:
                    print("  ! " + e)
                return 0 if info["valid"] else 1
            info = PLUG.set_enabled(K.EVO_ROOT, a.target, act == "enable")
        except (LookupError, ValueError, FileExistsError) as e:
            sys.exit(str(e))
        if a.json:
            print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, "ok": True, "plugin": PLUG.public(info)}, ensure_ascii=False)); return 0
        print(f"{info['name']}：{'已打开' if info['enabled'] else '已关掉'}" + ("" if info["valid"] else "（但 plugin.json 不合格：" + "；".join(info["errors"][:2]) + "）"))
        return 0
    if act == "validate":
        if a.target and os.path.isdir(a.target):
            infos = [PLUG.read_plugin(os.path.abspath(a.target))]
        elif a.target:
            i = PLUG.find(K.EVO_ROOT, a.target)
            if not i:
                sys.exit(f"没有插件 {a.target}（也不是目录）")
            infos = [i]
        else:
            infos = PLUG.discover(K.EVO_ROOT)
        bad = 0
        out = []
        for i in infos:
            errs = list(i["errors"])
            if i["valid"] and not i["compatible"]:
                errs.append(f"evo_api「{i['manifest'].get('evo_api')}」不兼容这版 evo")
            bad += bool(errs)
            out.append({"name": i["name"], "dir": i["dir"], "ok": not errs, "errors": errs})
        if a.json:
            print(json.dumps({"schema_version": K.APP_SCHEMA_VERSION, "ok": not bad, "plugins": out}, ensure_ascii=False))
        else:
            for o in out:
                print(("✓ " if o["ok"] else "✗ ") + o["name"] + ("" if o["ok"] else "：" + "；".join(o["errors"])))
            if not out:
                print("没有插件")
        return 1 if bad else 0
    if act == "run":
        if not (a.target and a.kind and a.cid):
            sys.exit("用法：evo plugin run <名字> sidebar_page|composer_command|notify_channel|item_action <id> [--args 文字] [--action A --payload JSON]")
        req = {"args": a.pargs or "", "action": a.paction, "project": a.project or (K.CODE if K.HAS_PROJECT else None), "item": a.item}
        if a.payload:
            try:
                req["payload"] = json.loads(a.payload)
            except ValueError:
                sys.exit("--payload 要是 JSON")
        if a.kind == "notify_channel":
            req["event"] = K.NOTE.event("test", "evo 插件通知测试", "收到这条说明插件通知渠道通了。", project=req["project"] or "*")
        r = PLUG.invoke(K.EVO_ROOT, a.target, a.kind, a.cid, req)
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        elif r["ok"]:
            print(json.dumps(r["card"], ensure_ascii=False, indent=1) if r["card"] else "好了")
        else:
            print("插件出错：" + (r["error"] or "?"), file=sys.stderr)
        return 0 if r["ok"] else 3
    return 2



class Host:
    """服务 plugins.host：给内核 / App 看第三方插件列表。"""

    @staticmethod
    def list():
        try:
            return PLUG.list_doc(K.EVO_ROOT).get("plugins") or []
        except Exception as e:
            return [{"error": str(e)[:200]}]


def _setup_cli(x):
    x.add_argument("action", choices=["list", "enable", "disable", "run", "validate", "install"])
    x.add_argument("target", nargs="?"); x.add_argument("kind", nargs="?"); x.add_argument("cid", nargs="?")
    x.add_argument("--json", action="store_true"); x.add_argument("--args", dest="pargs", default="")
    x.add_argument("--action", dest="paction"); x.add_argument("--payload"); x.add_argument("--project"); x.add_argument("--item")
    x.add_argument("--force", action="store_true")


def in_use(k, config):
    try:
        return sum(1 for p in PLUG.discover(k.EVO_ROOT) if p.get("enabled"))
    except Exception:
        return 0


def apply(ctx):
    global K
    K = ctx.k
    ctx.provide("plugins.host", Host)
    ctx.contribute("page", "plugins", {"title": "插件", "icon": "puzzlepiece.extension"})
    ctx.contribute("cli", "plugin", {"help": "第三方插件：list | enable <名> | disable <名> | run <名> <类型> <id> | validate [名|目录] | install <目录>",
                                     "setup": _setup_cli, "run": cmd_plugin, "no_project": True})
