"""evo 内核：功能包运行时（第十八轮，照 magpie 的 internal/pluginrt）。

内置功能 = kit/features/<id>/ 一个包：feature.json（manifest）+ feature.py（apply）。内核只认 manifest 和服务名，
从不 import 某个功能包（边界测试 test_round18.py::test_kernel_imports_no_feature 守着）。

manifest（feature.json）：
  id          小写字母数字连字符，和文件夹同名
  api         内核接口兼容范围，"^1"（API 现在是 1.0）
  name / sub  中文名、一句话（App 侧栏 / 设置里显示）
  essential   true = 「精简」预设下也开
  requires    要用的服务（内核提供 CORE_SERVICES；别的由其它功能包 provides）
  provides    它提供的服务名
  parts       [{slot, key, title?, icon?}]：它占的槽位。slot = cli（子命令）/ page（App 侧栏页）/ settings（设置区）/
              status（status --json 加字段）/ notify.channel（推送渠道）/ prompt.head（任务书开头）/ delivery.check（交卷检查）
  settings    JSON Schema 对象：properties 里每个设置一个 {type: boolean|integer|number|string, title, description?, enum?,
              minimum?, maximum?, default}；x-order 给显示顺序。App 按它自动画表单
  one / many  正在用时怎么说（"配了 1 个 Telegram 群" / "{n} 个 webhook"）
feature.py：
  apply(ctx)            必有：注册东西（ctx.provide / ctx.contribute / ctx.subscribe / ctx.on_dispose）
  in_use(k, config)     可选：返回整数，>0 表示正在用，关不掉（抛异常也算在用）

开关文件 ~/.evoloop/features.yml：preset（all | essentials）+ features 行 {id, enabled?, config?}，只存老板改过的。
合成顺序（magpie Compose）：默认全开 → 预设 → 老板的行 → 正在用的强制开。
生命周期：off / pending（等服务）/ active / failed（apply 抛错、API 不兼容；它注册过的全撤掉）/ disposed。
一个失败不影响别的。
"""
import importlib.util
import json
import os
import re
import sys

API_VERSION = (1, 0)
API = "1.0"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
CORE_SERVICES = ("core", "state", "config", "notify", "orca", "git", "bus", "clock")
SLOTS = ("cli", "page", "settings", "status", "notify.channel", "prompt.head", "delivery.check")
PRESETS = ("all", "essentials")
SETTING_TYPES = ("boolean", "integer", "number", "string")
STATES = ("off", "pending", "active", "failed", "disposed")
SETTLED = 1


class FeatureError(Exception):
    pass


# ---------- 版本范围：和第三方插件同一套语法（^1、>=1 <2、*）----------
def _ver(s):
    parts = s.split(".")
    if not 1 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        raise ValueError(s)
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def api_matches(spec, api=API_VERSION):
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
        ok &= {"": v[0] == x[0] and v >= x, "^": v[0] == x[0] and v >= x, "~": v[:2] == x[:2] and v >= x,
               "=": v == x, ">=": v >= x, "<=": v <= x, ">": v > x, "<": v < x}[op]
    return ok


# ---------- settings schema ----------
def check_schema(schema, where=""):
    """manifest 里的 settings 能不能画成表单。返回错误列表。"""
    errs = []
    if schema in (None, {}):
        return errs
    if not isinstance(schema, dict) or schema.get("type", "object") != "object" or not isinstance(schema.get("properties"), dict):
        return [f"{where}settings 要是 {{type: object, properties: {{…}}}}"]
    for k, p in schema["properties"].items():
        w = f"{where}settings.{k}："
        if not re.match(r"^[a-z][a-z0-9_]{0,39}$", k):
            errs.append(w + "键名只能小写字母数字下划线")
        if not isinstance(p, dict) or p.get("type") not in SETTING_TYPES:
            errs.append(w + f"type 只能是 {'/'.join(SETTING_TYPES)}（表单画不出别的）")
            continue
        if not isinstance(p.get("title"), str) or not p["title"].strip():
            errs.append(w + "缺 title")
        if "enum" in p and (not isinstance(p["enum"], list) or not p["enum"]):
            errs.append(w + "enum 要是非空列表")
        if "default" not in p:
            errs.append(w + "缺 default")
        elif validate_value(p, p["default"]) is not None:
            errs.append(w + "default 不合 schema")
    order = schema.get("x-order")
    if order is not None and (not isinstance(order, list) or set(order) != set(schema["properties"])):
        errs.append(f"{where}settings.x-order 要正好列出全部设置")
    return errs


def validate_value(p, v):
    """一个值合不合这一项 schema；合返回 None，不合返回原因。"""
    t = p.get("type")
    if t == "boolean" and not isinstance(v, bool):
        return "要是 true/false"
    if t == "integer" and (isinstance(v, bool) or not isinstance(v, int)):
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        else:
            return "要是整数"
    if t == "number" and (isinstance(v, bool) or not isinstance(v, (int, float))):
        return "要是数字"
    if t == "string" and not isinstance(v, str):
        return "要是文字"
    if "enum" in p and v not in p["enum"]:
        return f"只能是 {' / '.join(map(str, p['enum']))}"
    if t in ("integer", "number"):
        if "minimum" in p and v < p["minimum"]:
            return f"不能小于 {p['minimum']}"
        if "maximum" in p and v > p["maximum"]:
            return f"不能大于 {p['maximum']}"
    return None


def coerce(p, raw):
    """命令行 key=value 的字符串按 schema 转类型。"""
    t = p.get("type")
    if t == "boolean":
        if raw.lower() in ("true", "1", "on", "yes", "开"):
            return True
        if raw.lower() in ("false", "0", "off", "no", "关"):
            return False
        raise FeatureError(f"{raw} 不是 true/false")
    if t == "integer":
        try:
            return int(raw)
        except ValueError:
            raise FeatureError(f"{raw} 不是整数")
    if t == "number":
        try:
            return float(raw)
        except ValueError:
            raise FeatureError(f"{raw} 不是数字")
    return raw


def defaults_of(schema):
    return {k: p.get("default") for k, p in ((schema or {}).get("properties") or {}).items()}


# ---------- features.yml：一个够用的 YAML 子集（只认我们自己写出的形状；也认纯 JSON）----------
def _scalar(s):
    s = s.strip()
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", ""):
        return None
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d+$", s):
        return float(s)
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return json.loads(s) if s[0] == '"' else s[1:-1]
    return s


def parse_yml(text):
    t = text.strip()
    if t.startswith("{"):
        return json.loads(t)
    out, rows, row, sub = {}, None, None, None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #")[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        ind = len(line) - len(line.lstrip())
        body = line.strip()
        if ind == 0:
            if ":" not in body:
                raise ValueError(f"第 {n} 行看不懂：{raw}")
            k, v = body.split(":", 1)
            if k.strip() == "features" and not v.strip():
                rows = out["features"] = []
            else:
                out[k.strip()] = _scalar(v)
                rows = None
            continue
        if rows is None:
            raise ValueError(f"第 {n} 行缩进不对：{raw}")
        if body.startswith("- "):
            row = {}
            rows.append(row)
            sub = None
            body = body[2:].strip()
            ind += 2
        if row is None or ":" not in body:
            raise ValueError(f"第 {n} 行看不懂：{raw}")
        k, v = body.split(":", 1)
        k = k.strip()
        if ind <= 4 and k == "config" and not v.strip():
            sub = row["config"] = {}
        elif sub is not None and ind > 4:
            sub[k] = _scalar(v)
        else:
            row[k] = _scalar(v)
            sub = None
    return out


def _yv(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or re.search(r"[:#\-\[\]{},&*!|>'\"%@`]|^\s|\s$", s) or _scalar(s) != s:
        return json.dumps(s, ensure_ascii=False)
    return s


def dump_yml(doc):
    lines = ["# evo 功能开关（第十八轮）。evo feature on|off|set|preset 会改它；手改也行，改坏了 evo 会报错、不会当成空文件。",
             "# preset: all（默认，全部功能开）| essentials（只开 essential 的）。features 只记你改过的。",
             f"preset: {doc.get('preset', 'all')}", f"settled: {doc.get('settled', SETTLED)}", "features:"]
    for r in doc.get("features") or []:
        lines.append(f"  - id: {r['id']}")
        if "enabled" in r:
            lines.append(f"    enabled: {_yv(r['enabled'])}")
        if r.get("config"):
            lines.append("    config:")
            for k, v in r["config"].items():
                lines.append(f"      {k}: {_yv(v)}")
    return "\n".join(lines) + "\n"


# ---------- 运行时 ----------
class Feature:
    def __init__(self, fid, path, manifest, errors):
        self.id, self.dir, self.m, self.errors = fid, path, manifest, errors
        self.state, self.why = "off", ""
        self.module = None
        self.disposers = []
        self.provided = []
        self.in_use = 0
        self.in_use_err = None
        self.enabled = True
        self.chosen = None
        self.source = "default"
        self.config = {}
        self.config_source = {}
        self.applied_config = None


class Ctx:
    """apply(ctx) 拿到的东西。"""

    def __init__(self, rt, f):
        self._rt, self._f = rt, f
        self.id = f.id
        self.dir = f.dir
        self.config = dict(f.config)
        self.k = rt.kernel                # 内核接口（见 docs/architecture.md「内核接口」）
        self.bus = rt.bus
        self.data_dir = os.path.join(rt.root, "feature-data", f.id)

    def on_dispose(self, fn):
        self._f.disposers.append(fn)

    def provide(self, name, value):
        if name not in (self._f.m.get("provides") or []):
            raise FeatureError(f"{self.id} 没在 manifest provides 里声明服务 {name}")
        self._rt.services[name] = (self.id, value)
        self._f.provided.append(name)
        self.on_dispose(lambda: self._rt.services.pop(name, None))

    def service(self, name, default=None):
        return self._rt.service(name, default)

    def contribute(self, slot, key, value):
        if slot not in SLOTS:
            raise FeatureError(f"没有槽位 {slot}（只有 {', '.join(SLOTS)}）")
        bucket = self._rt.parts.setdefault(slot, {})
        bucket[key] = (self.id, value)
        self.on_dispose(lambda: bucket.pop(key, None) if bucket.get(key, (None,))[0] == self.id else None)

    def subscribe(self, event, fn, priority=50, timeout=30):
        off = self._rt.bus.subscribe(event, fn, owner=self.id, priority=priority, timeout=timeout) if self._rt.bus else (lambda: None)
        self.on_dispose(off)

    def publish(self, event, data=None, **kw):
        if self._rt.bus:
            return self._rt.bus.publish(event, data, **kw)


class Runtime:
    def __init__(self, features_dir, root, kernel=None, bus=None):
        self.features_dir = features_dir
        self.root = root
        self.kernel = kernel
        self.bus = bus
        self.path = os.path.join(root, "features.yml")
        self.features = {}           # id -> Feature
        self.services = {}           # name -> (fid, value)
        self.parts = {}              # slot -> {key: (fid, value)}
        self.file_error = None
        self.preset = "all"
        self.order = []              # apply 的先后（dispose 倒过来）
        self._mtime = None

    # ----- 发现 -----
    def discover(self):
        found = {}
        if os.path.isdir(self.features_dir):
            for name in sorted(os.listdir(self.features_dir)):
                d = os.path.join(self.features_dir, name)
                mp = os.path.join(d, "feature.json")
                if not os.path.isfile(mp):
                    continue
                try:
                    m = json.load(open(mp, encoding="utf-8"))
                except (OSError, ValueError) as e:
                    m, errs = {"id": name}, [f"feature.json 读不出：{e}"]
                else:
                    errs = validate_manifest(m, name)
                fid = m.get("id") if isinstance(m.get("id"), str) else name
                old = self.features.get(fid)
                if old and old.state == "active" and not errs:
                    found[fid] = old
                    continue
                found[fid] = Feature(fid, d, m, errs)
        self.features = found
        return found

    # ----- 文件 -----
    def load_file(self):
        if not os.path.exists(self.path):
            return {"preset": "all", "features": []}
        text = open(self.path, encoding="utf-8").read()
        doc = parse_yml(text)
        if not isinstance(doc, dict):
            raise ValueError("顶层要是映射")
        if doc.get("preset", "all") not in PRESETS:
            raise ValueError(f"preset 只能是 {' / '.join(PRESETS)}")
        rows = doc.get("features") or []
        if not isinstance(rows, list) or not all(isinstance(r, dict) and isinstance(r.get("id"), str) for r in rows):
            raise ValueError("features 要是 {id, enabled?, config?} 的列表")
        return doc

    def write_file(self, doc):
        if self.file_error:
            raise FeatureError(f"features.yml 坏了，先修好或删掉再改：{self.file_error}")
        os.makedirs(self.root, exist_ok=True)
        lock = open(self.path + ".lock", "w")
        try:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            if os.path.exists(self.path):
                try:
                    import shutil
                    shutil.copyfile(self.path, self.path + ".bak")
                except OSError:
                    pass
            doc["settled"] = SETTLED
            tmp = self.path + f".tmp{os.getpid()}"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(dump_yml(doc))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            lock.close()

    # ----- 合成 -----
    def compose(self):
        try:
            doc = self.load_file()
            self.file_error = None
        except (OSError, ValueError) as e:
            self.file_error = str(e)
            doc = {"preset": "all", "features": []}       # 第一次读好之前：全开（和没有这个文件一样）
        self.preset = doc.get("preset") or "all"
        rows = {r["id"]: r for r in doc.get("features") or []}
        for f in self.features.values():
            schema = f.m.get("settings") or {}
            cfg = defaults_of(schema)
            src = {k: "default" for k in cfg}
            on, why = True, "default"
            if self.preset == "essentials" and not f.m.get("essential"):
                on, why = False, "preset"
            r = rows.get(f.id) or {}
            if isinstance(r.get("enabled"), bool):
                on, why = r["enabled"], "user"
            f.chosen = on
            for k, v in (r.get("config") or {}).items():
                p = (schema.get("properties") or {}).get(k)
                if p is not None and validate_value(p, v) is None:     # 手改进来不合 schema 的值不要，默认值顶上
                    cfg[k] = v
                    src[k] = "user"
            f.config, f.config_source = cfg, src
            f.in_use, f.in_use_err = self._in_use(f)
            if f.in_use and not on:
                on, why = True, "in_use"
            f.enabled, f.source = on, why
        return doc

    def _in_use(self, f):
        if f.errors:
            return 0, None
        try:
            mod = self._module(f)
        except Exception:
            return 0, None                         # 代码都载不进来：apply 时会报 failed
        fn = getattr(mod, "in_use", None)
        if not fn:
            return 0, None
        try:
            return int(fn(self.kernel, f.config) or 0), None
        except Exception as e:                     # 读不准算在用（magpie：InUse 出错按在用，免得关掉后东西没人管）
            return 1, f"{type(e).__name__}: {e}"[:200]

    def _module(self, f):
        if f.module is None:
            py = os.path.join(f.dir, f.m.get("entry") or "feature.py")
            if f.dir not in sys.path:
                sys.path.insert(0, f.dir)
            spec = importlib.util.spec_from_file_location("evo_feature_" + f.id.replace("-", "_"), py)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            f.module = mod
        return f.module

    # ----- 生命周期 -----
    def reconcile(self):
        """先关：不要的 + 依赖被关掉服务的（新的先关）；再开：要的、依赖齐了的，一遍遍直到开不动。"""
        want = {fid for fid, f in self.features.items() if f.enabled and not f.errors}
        changed = True
        while changed:
            changed = False
            for fid in reversed(list(self.order)):
                f = self.features.get(fid)
                if f is None or fid not in want or any(self._provider(r) is None for r in f.m.get("requires") or []):
                    self._dispose(fid, "off" if fid not in want else "pending")
                    changed = True
                elif f.applied_config != f.config:          # 设置变了：撤掉重来（apply 拿新设置）
                    self._dispose(fid, "pending")
                    changed = True
        for f in self.features.values():
            if f.errors:
                f.state, f.why = "failed", "；".join(f.errors)[:300]
            elif f.id not in want and f.state != "disposed":
                f.state, f.why = "off", {"preset": "精简预设没开它", "user": "你关了它"}.get(f.source, "关")
        progress = True
        while progress:
            progress = False
            for fid in sorted(want):
                f = self.features[fid]
                if f.state == "active":
                    continue
                missing = [r for r in f.m.get("requires") or [] if self._provider(r) is None]
                if missing:
                    f.state, f.why = "pending", "等服务：" + "、".join(missing)
                    continue
                if f.state == "failed" and f.why.startswith("apply"):
                    continue
                self._apply(f)
                if f.state == "active":
                    progress = True
        return self

    def _provider(self, name):
        if name in CORE_SERVICES:
            return "core"
        return self.services.get(name, (None,))[0]

    def _apply(self, f):
        try:
            if not api_matches(f.m.get("api", ""), API_VERSION):
                f.state, f.why = "failed", f"要的内核接口 {f.m.get('api')} 和现在的 {API} 不兼容"
                return
        except ValueError:
            f.state, f.why = "failed", f"api 写法不对：{f.m.get('api')}"
            return
        f.disposers, f.provided = [], []
        try:
            mod = self._module(f)
            if not hasattr(mod, "apply"):
                raise FeatureError("feature.py 没有 apply(ctx)")
            mod.apply(Ctx(self, f))
        except BaseException as e:
            self._undo(f)
            f.state, f.why = "failed", f"apply 出错：{type(e).__name__}: {e}"[:300]
            return
        missing = [p for p in f.m.get("provides") or [] if p not in f.provided]
        if missing:
            self._undo(f)
            f.state, f.why = "failed", "manifest 说会提供但没提供：" + "、".join(missing)
            return
        f.state, f.why = "active", ""
        f.applied_config = dict(f.config)
        self.order.append(f.id)

    def _undo(self, f):
        for fn in reversed(f.disposers):
            try:
                fn()
            except BaseException as e:
                print(f"功能包 {f.id} 撤销时出错：{e}", file=sys.stderr)
        f.disposers, f.provided = [], []
        if self.bus:
            self.bus.drop_owner(f.id)

    def _dispose(self, fid, state):
        f = self.features.get(fid)
        if f:
            self._undo(f)
            f.state = state
        if fid in self.order:
            self.order.remove(fid)

    def refresh(self, force=False):
        """读 features.yml、合成、对齐。常驻进程每轮调；文件没变就不动（force 例外）。"""
        try:
            mt = os.path.getmtime(self.path) if os.path.exists(self.path) else 0
        except OSError:
            mt = None
        if not force and self._mtime is not None and mt == self._mtime:
            return self
        self._mtime = mt
        self.discover()
        self.compose()
        return self.reconcile()

    # ----- 内核用 -----
    def service(self, name, default=None):
        v = self.services.get(name)
        return v[1] if v else default

    def contributions(self, slot):
        return [(fid, key, val) for key, (fid, val) in sorted((self.parts.get(slot) or {}).items())]

    def contribution(self, slot, key):
        v = (self.parts.get(slot) or {}).get(key)
        return v[1] if v else None

    def active(self, fid):
        f = self.features.get(fid)
        return bool(f and f.state == "active")

    def owner_of_part(self, slot, key):
        """哪个功能包的 manifest 声明了这个槽位（不管开没开）：关掉时内核好说「功能 X 关着」。"""
        for f in self.features.values():
            for p in f.m.get("parts") or []:
                if p.get("slot") == slot and p.get("key") == key:
                    return f
        return None

    # ----- 改开关 / 设置 -----
    def _rows(self):
        if self.file_error:
            raise FeatureError(f"features.yml 坏了，先修好或删掉再改：{self.file_error}")
        try:
            doc = self.load_file()
        except (OSError, ValueError) as e:
            raise FeatureError(f"features.yml 坏了，先修好或删掉再改：{e}")
        rows = doc.setdefault("features", [])
        return doc, rows

    def set_enabled(self, fid, on):
        f = self.features.get(fid)
        if not f:
            raise FeatureError(f"没有功能 {fid}（evo feature list 看有哪些）")
        if not on and f.in_use:
            raise FeatureError(f"{fid} 正在用（{self.in_use_text(f)}），关不掉：先把用到它的东西撤了")
        doc, rows = self._rows()
        row = next((r for r in rows if r["id"] == fid), None)
        if row is None:
            row = {"id": fid}
            rows.append(row)
        row["enabled"] = bool(on)
        self.write_file(doc)
        self._mtime = None
        self.refresh(force=True)
        return f

    def set_config(self, fid, values):
        f = self.features.get(fid)
        if not f:
            raise FeatureError(f"没有功能 {fid}")
        props = ((f.m.get("settings") or {}).get("properties") or {})
        for k, v in values.items():
            if k not in props:
                raise FeatureError(f"{fid} 没有设置 {k}（有：{', '.join(props) or '无'}）")
            why = validate_value(props[k], v)
            if why:
                raise FeatureError(f"{fid}.{k} {why}")
        doc, rows = self._rows()
        row = next((r for r in rows if r["id"] == fid), None)
        if row is None:
            row = {"id": fid}
            rows.append(row)
        cfg = dict(row.get("config") or {})
        for k, v in values.items():
            if v == props[k].get("default"):
                cfg.pop(k, None)          # 改回默认就不记
            else:
                cfg[k] = v
        if cfg:
            row["config"] = cfg
        else:
            row.pop("config", None)
        if set(row) == {"id"}:
            rows.remove(row)
        self.write_file(doc)
        self._mtime = None
        self.refresh(force=True)
        return f

    def set_preset(self, preset):
        if preset not in PRESETS:
            raise FeatureError(f"预设只能是 {' / '.join(PRESETS)}")
        doc, _ = self._rows()
        doc["preset"] = preset
        self.write_file(doc)
        self._mtime = None
        self.refresh(force=True)

    def in_use_text(self, f):
        n = f.in_use
        if not n:
            return ""
        if f.in_use_err:
            return f"读不准是否在用（{f.in_use_err}），按在用算"
        if n == 1 and f.m.get("one"):
            return f.m["one"]
        return (f.m.get("many") or "{n} 处在用").replace("{n}", str(n))

    # ----- dump -----
    def dump(self):
        out = []
        for fid in sorted(self.features):
            f = self.features[fid]
            m = f.m
            out.append({"id": fid, "name": m.get("name") or fid, "sub": m.get("sub") or "", "version": m.get("version") or "1",
                        "api": m.get("api"), "essential": bool(m.get("essential")), "state": f.state, "why": f.why,
                        "enabled": f.enabled, "chosen": f.chosen, "source": f.source,
                        "in_use": f.in_use, "in_use_text": self.in_use_text(f),
                        "requires": m.get("requires") or [], "provides": m.get("provides") or [],
                        "parts": m.get("parts") or [], "settings": m.get("settings") or None,
                        "config": f.config, "config_source": f.config_source,
                        "subscribes": [x["pattern"] for x in (self.bus.subscribers() if self.bus else []) if x["owner"] == fid]})
        return out


def validate_manifest(m, dirname=None):
    errs = []
    if not isinstance(m, dict):
        return ["feature.json 要是对象"]
    fid = m.get("id")
    if not isinstance(fid, str) or not ID_RE.match(fid):
        errs.append("id 只能小写字母、数字、连字符（≤40）")
    elif dirname and fid != dirname:
        errs.append(f"id {fid} 要和文件夹名 {dirname} 一样")
    try:
        if not api_matches(m.get("api", ""), API_VERSION):
            pass                      # 不兼容在 apply 时报 failed，不算 manifest 写错
    except ValueError:
        errs.append(f"api 写法不对：{m.get('api')!r}（例 ^1）")
    if not isinstance(m.get("name"), str) or not m["name"].strip():
        errs.append("缺 name")
    for k in ("requires", "provides"):
        v = m.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and re.match(r"^[a-z][a-z0-9_.-]{0,63}$", x) for x in v):
            errs.append(f"{k} 要是服务名列表")
    for p in m.get("provides") or []:
        if p in CORE_SERVICES:
            errs.append(f"provides 不能占内核服务名 {p}")
    parts = m.get("parts", [])
    if not isinstance(parts, list):
        errs.append("parts 要是列表")
    else:
        for p in parts:
            if not isinstance(p, dict) or p.get("slot") not in SLOTS or not isinstance(p.get("key"), str):
                errs.append(f"parts 里每项要是 {{slot: {'|'.join(SLOTS)}, key}}：{p!r}"[:200])
    errs += check_schema(m.get("settings"))
    return errs
