"""evo 插件（第十六轮）：丢一个文件夹进 ~/.evoloop/plugins/<名字>/，App 就多一个侧栏页 / 输入框命令 / 通知渠道，不用改 App 本体。

参考的成熟做法（只借形状，不自造协议）：
  * manifest：VS Code 扩展的 package.json —— `engines.vscode` 兼容范围 → 这里的 `evo_api`；`contributes.<贡献点>` 列表 → 这里的
    `contributes.sidebar_pages / composer_commands / notify_channels / item_actions`。
  * 执行：git / kubectl 插件那种「插件就是一个外部可执行文件，作为子进程跑」，退出码 0 = 成功。
  * 输入输出：一次性的 JSON over stdio（像 git credential helper、Terraform external data source）：
    evo 往插件 stdin 写一个请求 JSON，插件往 stdout 写一个卡片 JSON，然后退出。没用 JSON-RPC：一问一答、无状态，够用且最不容易出错。
安全：插件一律子进程跑，有超时（默认 20 秒，最多 60）、输出上限（256 KB）、环境变量白名单（拿不到任何密钥类环境变量）；
新插件默认关着，要老板在设置里打开或 `evo plugin enable`；外部 Agent（EVO_AGENT）不能开关、安装插件。
插件失败只回一条错误（App 在该页显示），不影响 App 和 evo 主循环。文档：docs/plugins.md、docs/app-contract.md。
"""
import json, os, re, shutil, signal, subprocess, sys, threading, time

API_VERSION = (1, 0)          # 插件接口版本：manifest 的 evo_api 范围要包含它
CARD_SCHEMA = 1               # 卡片 JSON 的 schema_version
CONTRACT_SCHEMA = 1           # plugin list / run 输出的 schema_version
KINDS = {                     # 命令行 / 请求里的单数名 → manifest 里的贡献点（复数，VS Code 写法）
    "sidebar_page": "sidebar_pages",
    "composer_command": "composer_commands",
    "notify_channel": "notify_channels",
    "item_action": "item_actions",
}
DEFAULT_TIMEOUT, MAX_TIMEOUT = 20, 60
MAX_OUTPUT = 256 * 1024
MAX_STDERR = 16 * 1024
MAX_TEXT = 2000
ENV_ALLOW = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR", "USER", "LOGNAME")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
CMD_RE = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
# 输入框里这些词已经有意思了（或以后会用），插件不能占
RESERVED_COMMANDS = {"help", "add", "feedback", "team", "evo", "plugin", "plugins", "settings", "tick", "ship", "approve"}
TEXT_STYLES = {"body", "caption", "title", "mono"}
TONES = {"neutral", "accent", "success", "warning", "danger"}
BUTTON_STYLES = {"primary", "secondary", "danger"}
LIMITS = {"blocks": 50, "list": 200, "rows": 200, "cols": 12, "buttons": 6}


# ---------- 位置 ----------
def plugins_dir(evo_root):
    return os.environ.get("EVO_PLUGINS_DIR") or os.path.join(evo_root, "plugins")


def data_dir(evo_root, name):
    return os.path.join(evo_root, "plugin-data", name)


# ---------- 版本范围（npm/semver 的子集：1 | ^1 | >=1 <2 | >=1.0,<3 | *）----------
def _ver(s):
    parts = s.split(".")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        raise ValueError(s)
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def api_matches(spec, api=API_VERSION):
    """spec 能不能装 api 版本。语法错抛 ValueError。"""
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("空")
    v = tuple(api) + (0,) * (3 - len(api))
    if spec == "*":
        return True
    ok = True
    for tok in re.split(r"[\s,]+", spec):
        if not tok:
            continue
        m = re.match(r"^(\^|~|>=|<=|>|<|=)?(\d+(?:\.\d+){0,2})$", tok)
        if not m:
            raise ValueError(tok)
        op, x = m.group(1) or "", _ver(m.group(2))
        if op in ("", "^"):
            ok &= v[0] == x[0] and v >= x
        elif op == "~":
            ok &= v[:2] == x[:2] and v >= x
        elif op == "=":
            ok &= v == x
        elif op == ">=":
            ok &= v >= x
        elif op == "<=":
            ok &= v <= x
        elif op == ">":
            ok &= v > x
        elif op == "<":
            ok &= v < x
    return ok


# ---------- manifest ----------
def _str(d, k, errs, where, required=True, maxlen=200):
    v = d.get(k)
    if v is None:
        if required:
            errs.append(f"{where}缺 {k}")
        return None
    if not isinstance(v, str) or not v.strip():
        errs.append(f"{where}{k} 要是非空字符串")
        return None
    return v.strip()[:maxlen]


def validate_manifest(m, dirname=None):
    """检查 plugin.json。返回 (整理后的 manifest, 错误列表)。整理后：缺省值补齐、多余字段原样保留。"""
    errs = []
    if not isinstance(m, dict):
        return None, ["plugin.json 顶层要是对象"]
    out = dict(m)
    name = _str(m, "name", errs, "")
    if name and not NAME_RE.match(name):
        errs.append("name 只能是小写字母、数字、连字符（≤40 字符），例 example-hello")
    if name and dirname and name != dirname:
        errs.append(f"name「{name}」要和文件夹名「{dirname}」一样")
    _str(m, "version", errs, "")
    spec = _str(m, "evo_api", errs, "")
    compatible = False
    if spec:
        try:
            compatible = api_matches(spec)
        except ValueError:
            errs.append(f"evo_api「{spec}」看不懂（写法例：^1、>=1 <2）")
    if "enabled" in m and not isinstance(m["enabled"], bool):
        errs.append("enabled 要是 true / false")
    out["enabled"] = m.get("enabled") is True
    if "timeout_seconds" in m and not (isinstance(m["timeout_seconds"], int) and 1 <= m["timeout_seconds"] <= MAX_TIMEOUT):
        errs.append(f"timeout_seconds 要是 1–{MAX_TIMEOUT} 的整数")
    c = m.get("contributes")
    if not isinstance(c, dict) or not c:
        errs.append("contributes 要是对象，至少一个贡献点")
        c = {}
    for k in c:
        if k not in KINDS.values():
            errs.append(f"contributes 里不认识「{k}」（只认 {'、'.join(KINDS.values())}）")
    contrib = {}
    seen_cmd = set()
    for kind, key in KINDS.items():
        lst = c.get(key) or []
        if not isinstance(lst, list):
            errs.append(f"contributes.{key} 要是列表"); continue
        ids = set()
        norm = []
        for i, e in enumerate(lst):
            w = f"contributes.{key}[{i}] "
            if not isinstance(e, dict):
                errs.append(w + "要是对象"); continue
            e = dict(e)
            cid = _str(e, "id", errs, w)
            if cid and not NAME_RE.match(cid):
                errs.append(w + "id 只能是小写字母、数字、连字符")
            if cid in ids:
                errs.append(w + f"id「{cid}」重复")
            ids.add(cid)
            _str(e, "title", errs, w, maxlen=40)
            run = e.get("run")
            if not (isinstance(run, list) and run and all(isinstance(x, str) and x for x in run)):
                errs.append(w + "run 要是非空字符串列表，例 [\"python3\", \"hello.py\", \"page\"]")
            if "timeout_seconds" in e and not (isinstance(e["timeout_seconds"], int) and 1 <= e["timeout_seconds"] <= MAX_TIMEOUT):
                errs.append(w + f"timeout_seconds 要是 1–{MAX_TIMEOUT} 的整数")
            if kind == "composer_command":
                nm = _str(e, "name", errs, w, maxlen=24)
                if nm and not CMD_RE.match(nm):
                    errs.append(w + "name 只能是小写字母开头的字母、数字、连字符（≤24），输入框里打「/名字」")
                elif nm in RESERVED_COMMANDS:
                    errs.append(w + f"name「{nm}」是保留词")
                elif nm in seen_cmd:
                    errs.append(w + f"name「{nm}」重复")
                seen_cmd.add(nm)
            if kind == "notify_channel":
                e["events"] = e.get("events") or "push"
                if e["events"] not in ("push", "all"):
                    errs.append(w + "events 只能是 push 或 all")
            norm.append(e)
        contrib[key] = norm
    out["contributes"] = contrib
    out["_compatible"] = compatible
    return out, errs


def read_plugin(path):
    """读一个插件文件夹。返回 dict：name、dir、manifest（整理后，可能 None）、errors、compatible、enabled、active。"""
    dirname = os.path.basename(os.path.normpath(path))
    mp = os.path.join(path, "plugin.json")
    info = {"name": dirname, "dir": path, "manifest": None, "errors": [], "compatible": False, "enabled": False}
    try:
        raw = json.load(open(mp, encoding="utf-8"))
    except FileNotFoundError:
        info["errors"] = ["没有 plugin.json"]; return _fin(info)
    except ValueError as e:
        info["errors"] = [f"plugin.json 不是合法 JSON：{e}"]; return _fin(info)
    m, errs = validate_manifest(raw, dirname)
    info["manifest"] = m
    info["errors"] = errs
    if m:
        info["compatible"] = m.pop("_compatible", False)
        info["enabled"] = m["enabled"]
    return _fin(info)


def _fin(info):
    info["valid"] = not info["errors"]
    info["active"] = info["valid"] and info["compatible"] and info["enabled"]
    return info


def discover(evo_root):
    d = plugins_dir(evo_root)
    if not os.path.isdir(d):
        return []
    out = []
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if os.path.isdir(p) and not n.startswith("."):
            out.append(read_plugin(p))
    return out


def find(evo_root, name):
    for p in discover(evo_root):
        if p["name"] == name:
            return p
    return None


def public(info):
    """plugin list --json 里一个插件的样子（docs/app-contract.md「plugin list」）。不带 run 命令行。"""
    m = info["manifest"] or {}
    c = m.get("contributes") or {}

    def pick(lst, keys):
        return [{k: e.get(k) for k in keys if e.get(k) is not None} for e in lst]
    return {
        "name": info["name"], "version": m.get("version"), "description": m.get("description"),
        "evo_api": m.get("evo_api"), "enabled": info["enabled"], "valid": info["valid"],
        "compatible": info["compatible"], "active": info["active"], "errors": info["errors"],
        "contributes": {
            "sidebar_pages": pick(c.get("sidebar_pages") or [], ("id", "title", "icon")),
            "composer_commands": pick(c.get("composer_commands") or [], ("id", "name", "title", "description", "usage")),
            "notify_channels": pick(c.get("notify_channels") or [], ("id", "title", "events")),
            "item_actions": pick(c.get("item_actions") or [], ("id", "title", "icon")),
        },
    }


def list_doc(evo_root):
    return {"schema_version": CONTRACT_SCHEMA, "evo_api": "%d.%d" % API_VERSION, "plugins_dir": plugins_dir(evo_root),
            "plugins": [public(p) for p in discover(evo_root)]}


def set_enabled(evo_root, name, on):
    p = find(evo_root, name)
    if not p:
        raise LookupError(f"没有插件 {name}（{plugins_dir(evo_root)}）")
    mp = os.path.join(p["dir"], "plugin.json")
    raw = json.load(open(mp, encoding="utf-8"))
    raw["enabled"] = bool(on)
    tmp = mp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, mp)
    return read_plugin(p["dir"])


def install(evo_root, src, force=False):
    """把一个插件文件夹拷进插件目录；一律先关着（enabled=false），要老板自己开。"""
    src = os.path.abspath(src)
    info = read_plugin(src)
    if not info["manifest"] or not info["manifest"].get("name"):
        raise ValueError("不是插件文件夹：" + "；".join(info["errors"]))
    name = info["manifest"]["name"]
    if not NAME_RE.match(name):
        raise ValueError("插件名不合格：" + name)
    dst = os.path.join(plugins_dir(evo_root), name)
    if os.path.exists(dst):
        if not force:
            raise FileExistsError(f"已经有 {name}；要覆盖加 --force")
        shutil.rmtree(dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    raw = json.load(open(os.path.join(dst, "plugin.json"), encoding="utf-8"))
    raw["enabled"] = False
    json.dump(raw, open(os.path.join(dst, "plugin.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return read_plugin(dst)


# ---------- 卡片 ----------
def _t(v):
    return v if len(v) <= MAX_TEXT else v[:MAX_TEXT - 1] + "…"


def validate_card(c):
    """检查插件输出的卡片 JSON（kit/schemas/card.schema.json 的同一套规则，不依赖 jsonschema）。
    返回 (整理后的卡片, 错误列表)。超长文字截断，不算错；超过条数上限算错。"""
    errs = []
    if not isinstance(c, dict):
        return None, ["卡片要是 JSON 对象"]
    sv = c.get("schema_version", CARD_SCHEMA)
    if sv != CARD_SCHEMA:
        errs.append(f"卡片 schema_version 是 {sv}，这版 evo 只认 {CARD_SCHEMA}")
    title = c.get("title")
    if not isinstance(title, str) or not title.strip():
        errs.append("卡片缺 title（非空字符串）")
        title = ""
    out = {"schema_version": CARD_SCHEMA, "title": _t(title.strip())}
    if c.get("subtitle") is not None:
        if isinstance(c["subtitle"], str):
            out["subtitle"] = _t(c["subtitle"])
        else:
            errs.append("subtitle 要是字符串")
    blocks = c.get("blocks", [])
    if not isinstance(blocks, list):
        errs.append("blocks 要是列表"); blocks = []
    if len(blocks) > LIMITS["blocks"]:
        errs.append(f"blocks 最多 {LIMITS['blocks']} 块")
    nb = []
    for i, b in enumerate(blocks[:LIMITS["blocks"]]):
        w = f"blocks[{i}] "
        if not isinstance(b, dict):
            errs.append(w + "要是对象"); continue
        tp = b.get("type")
        if tp == "text":
            if not isinstance(b.get("text"), str):
                errs.append(w + "text 块要有 text 字符串"); continue
            x = {"type": "text", "text": _t(b["text"]), "style": b.get("style") or "body"}
            if x["style"] not in TEXT_STYLES:
                errs.append(w + f"style 只能是 {'/'.join(sorted(TEXT_STYLES))}")
            if b.get("tone") is not None:
                x["tone"] = b["tone"]
                if b["tone"] not in TONES:
                    errs.append(w + f"tone 只能是 {'/'.join(sorted(TONES))}")
        elif tp == "list":
            items = b.get("items")
            if not isinstance(items, list):
                errs.append(w + "list 块要有 items 列表"); continue
            if len(items) > LIMITS["list"]:
                errs.append(w + f"items 最多 {LIMITS['list']} 条")
            xs = []
            for j, it in enumerate(items[:LIMITS["list"]]):
                if not isinstance(it, dict) or not isinstance(it.get("title"), str):
                    errs.append(w + f"items[{j}] 要有 title 字符串"); continue
                y = {"title": _t(it["title"])}
                for k in ("subtitle", "badge", "symbol"):
                    if it.get(k) is not None:
                        if isinstance(it[k], str):
                            y[k] = _t(it[k])
                        else:
                            errs.append(w + f"items[{j}].{k} 要是字符串")
                if it.get("tone") is not None:
                    y["tone"] = it["tone"]
                    if it["tone"] not in TONES:
                        errs.append(w + f"items[{j}].tone 不认识")
                xs.append(y)
            x = {"type": "list", "items": xs}
        elif tp == "table":
            cols, rows = b.get("columns"), b.get("rows")
            if not (isinstance(cols, list) and cols and all(isinstance(s, str) for s in cols)):
                errs.append(w + "table 块要有 columns 字符串列表"); continue
            if len(cols) > LIMITS["cols"]:
                errs.append(w + f"columns 最多 {LIMITS['cols']} 列")
            if not isinstance(rows, list):
                errs.append(w + "table 块要有 rows 列表"); continue
            if len(rows) > LIMITS["rows"]:
                errs.append(w + f"rows 最多 {LIMITS['rows']} 行")
            rs = []
            for j, r in enumerate(rows[:LIMITS["rows"]]):
                if not isinstance(r, list) or not all(isinstance(s, (str, int, float)) and not isinstance(s, bool) for s in r):
                    errs.append(w + f"rows[{j}] 要是字符串/数字列表"); continue
                r = [_t(str(s)) for s in r][:len(cols)]
                rs.append(r + [""] * (len(cols) - len(r)))
            x = {"type": "table", "columns": [_t(s) for s in cols[:LIMITS["cols"]]], "rows": [r[:LIMITS["cols"]] for r in rs]}
        elif tp == "buttons":
            bs = b.get("buttons")
            if not isinstance(bs, list) or not bs:
                errs.append(w + "buttons 块要有非空 buttons 列表"); continue
            if len(bs) > LIMITS["buttons"]:
                errs.append(w + f"buttons 最多 {LIMITS['buttons']} 个")
            ys = []
            for j, bt in enumerate(bs[:LIMITS["buttons"]]):
                if not isinstance(bt, dict) or not isinstance(bt.get("label"), str) or not isinstance(bt.get("action"), str) \
                        or not bt["action"].strip():
                    errs.append(w + f"buttons[{j}] 要有 label 和 action 字符串"); continue
                y = {"label": _t(bt["label"])[:40], "action": bt["action"][:64], "style": bt.get("style") or "secondary"}
                if y["style"] not in BUTTON_STYLES:
                    errs.append(w + f"buttons[{j}].style 只能是 primary/secondary/danger")
                if bt.get("payload") is not None:
                    y["payload"] = bt["payload"]
                    if len(json.dumps(bt["payload"], ensure_ascii=False)) > 4096:
                        errs.append(w + f"buttons[{j}].payload 太大（≤4KB）")
                ys.append(y)
            x = {"type": "buttons", "buttons": ys}
        else:
            errs.append(w + f"不认识的块 type「{tp}」（只认 text / list / table / buttons）"); continue
        nb.append(x)
    out["blocks"] = nb
    return out, errs


# ---------- 子进程 ----------
def plugin_env(evo_root, info):
    e = {k: os.environ[k] for k in ENV_ALLOW if os.environ.get(k)}
    e.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    e.setdefault("LANG", "zh_CN.UTF-8")
    dd = data_dir(evo_root, info["name"])
    os.makedirs(dd, exist_ok=True)
    e.update({"EVO_API": "%d.%d" % API_VERSION, "EVO_PLUGIN_NAME": info["name"], "EVO_PLUGIN_DIR": info["dir"],
              "EVO_PLUGIN_DATA": dd, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    return e


def resolve_argv(run, plugin_dir, path_env):
    """run 的第一个词：python3/python → 跑 evo 的同一个 python；含 / 或插件目录里有这个文件 → 插件目录里的；否则在 PATH 里找。"""
    exe, rest = run[0], list(run[1:])
    if exe in ("python3", "python"):
        exe = sys.executable
    elif "/" in exe or os.path.exists(os.path.join(plugin_dir, exe)):
        exe = exe if os.path.isabs(exe) else os.path.join(plugin_dir, exe)
    else:
        exe = shutil.which(exe, path=path_env) or exe
    return [exe] + rest


def run_process(argv, cwd, stdin_bytes, timeout, env, max_out=MAX_OUTPUT):
    """跑一个子进程：自己一个进程组（超时整组杀掉），stdout 超过上限立即杀，stderr 只留尾巴。"""
    t0 = time.time()
    try:
        p = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=env, start_new_session=True)
    except OSError as e:
        return {"code": -1, "out": b"", "err": f"起不来：{e}", "timed_out": False, "too_big": False, "ms": 0}
    box = {"out": bytearray(), "err": bytearray(), "too_big": False}

    def kill():
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                p.kill()
            except OSError:
                pass

    def rd_out():
        while True:
            ch = p.stdout.read1(65536) if hasattr(p.stdout, "read1") else p.stdout.read(65536)
            if not ch:
                break
            box["out"] += ch
            if len(box["out"]) > max_out:
                box["too_big"] = True
                kill()
                break

    def rd_err():
        while True:
            ch = p.stderr.read(4096)
            if not ch:
                break
            box["err"] = (box["err"] + ch)[-MAX_STDERR:]

    def wr():
        try:
            p.stdin.write(stdin_bytes or b"")
        except (BrokenPipeError, OSError):
            pass
        try:
            p.stdin.close()
        except OSError:
            pass
    ts = [threading.Thread(target=f, daemon=True) for f in (rd_out, rd_err, wr)]
    for t in ts:
        t.start()
    timed_out = False
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    for t in ts:
        t.join(timeout=2)
    return {"code": p.returncode, "out": bytes(box["out"][:max_out]), "err": box["err"].decode("utf-8", "replace"),
            "timed_out": timed_out, "too_big": box["too_big"], "ms": int((time.time() - t0) * 1000)}


def contribution(info, kind, cid):
    key = KINDS.get(kind)
    if not key:
        raise ValueError(f"不认识的类型 {kind}（只认 {'、'.join(KINDS)}）")
    for e in ((info["manifest"] or {}).get("contributes") or {}).get(key) or []:
        if e.get("id") == cid or (kind == "composer_command" and e.get("name") == cid):
            return e
    raise LookupError(f"插件 {info['name']} 没有 {kind}「{cid}」")


def invoke(evo_root, name, kind, cid, request=None, require_active=True):
    """跑一个贡献点，返回 plugin run 的信封（docs/app-contract.md「plugin run」）。永远不抛异常。"""
    env_ = {"schema_version": CONTRACT_SCHEMA, "ok": False, "plugin": name, "kind": kind, "id": cid, "card": None,
            "error": None, "elapsed_ms": 0, "stderr_tail": ""}
    try:
        info = find(evo_root, name)
        if not info:
            env_["error"] = f"没有插件 {name}"; return env_
        if not info["valid"]:
            env_["error"] = "plugin.json 不合格：" + "；".join(info["errors"][:3]); return env_
        if not info["compatible"]:
            env_["error"] = f"插件要的 evo_api「{info['manifest'].get('evo_api')}」和这版 evo（{'%d.%d' % API_VERSION}）不兼容"; return env_
        if require_active and not info["enabled"]:
            env_["error"] = f"插件 {name} 还没打开（设置里打开，或 evo plugin enable {name}）"; return env_
        c = contribution(info, kind, cid)
        env_["id"] = c["id"]
        req = {"evo_api": "%d.%d" % API_VERSION, "plugin": name, "kind": kind, "id": c["id"],
               "action": None, "payload": None, "args": "", "project": None, "item": None, "event": None}
        req.update({k: v for k, v in (request or {}).items() if k in req and k not in ("evo_api", "plugin", "kind", "id")})
        timeout = c.get("timeout_seconds") or info["manifest"].get("timeout_seconds") or DEFAULT_TIMEOUT
        penv = plugin_env(evo_root, info)
        argv = resolve_argv(c["run"], info["dir"], penv["PATH"])
        r = run_process(argv, info["dir"], json.dumps(req, ensure_ascii=False).encode("utf-8"), min(timeout, MAX_TIMEOUT), penv)
        env_["elapsed_ms"] = r["ms"]
        env_["stderr_tail"] = r["err"][-500:]
        if r["timed_out"]:
            env_["error"] = f"插件超时（{timeout} 秒），已停掉"; return env_
        if r["too_big"]:
            env_["error"] = f"插件输出超过 {MAX_OUTPUT // 1024} KB，已停掉"; return env_
        if r["code"] != 0:
            tail = (r["err"].strip().splitlines() or [""])[-1][:200]
            env_["error"] = f"插件退出码 {r['code']}" + (f"：{tail}" if tail else ""); return env_
        if kind == "notify_channel":
            env_["ok"] = True; return env_
        text = r["out"].decode("utf-8", "replace").strip()
        try:
            card = json.loads(text)
        except ValueError:
            env_["error"] = "插件输出不是 JSON：" + (text[:120] or "（空）"); return env_
        card, errs = validate_card(card)
        if errs:
            env_["error"] = "插件输出的卡片不合格：" + "；".join(errs[:3]); return env_
        env_["ok"] = True
        env_["card"] = card
        return env_
    except Exception as e:                      # 插件的事永远不能拖垮 evo
        env_["error"] = f"{type(e).__name__}: {e}"
        return env_


def notify(evo_root, ev, push):
    """evo_notify 发推送时调：每个打开的插件的 notify_channels 各跑一次，事件 JSON 从 stdin 给。
    push=True：要推的事（已过免打扰），所有渠道都收；push=False：info 事件，只有 events=all 的渠道收。返回 {渠道名: 成功否}。"""
    res = {}
    try:
        plugins = [p for p in discover(evo_root) if p["active"]]
    except Exception:
        return res
    for p in plugins:
        for ch in p["manifest"]["contributes"].get("notify_channels") or []:
            if not push and ch.get("events") != "all":
                continue
            r = invoke(evo_root, p["name"], "notify_channel", ch["id"], {"event": ev, "project": ev.get("project")})
            res[f"plugin:{p['name']}/{ch['id']}"] = r["ok"]
            if not r["ok"]:
                print(f"插件通知渠道 {p['name']}/{ch['id']} 没发出去：{r['error']}", file=sys.stderr)
    return res
