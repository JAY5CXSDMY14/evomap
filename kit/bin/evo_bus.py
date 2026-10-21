"""evo 内核：事件总线（第十八轮）。

发布 / 订阅。内核在固定的点发事件（件建好了、开工、交卷、验收没过、闸门等你、闸门结了、上线、每一轮……），
功能包订阅它们做自己的事。规矩：

- 每个订阅者单独兜错：一个功能包抛异常 / 超时，只记一条 feature.error，别的订阅者和内核照常。
- 有超时：订阅时给 timeout 秒（默认 30）；超时就不等了（线程放着，记错）。timeout=0 表示同步直接调（内核自己的快订阅者用）。
- 按 priority 从小到大调；同优先级按订阅先后。
- 每个事件（除非 record=False）追加一行到 ~/.evoloop/events.jsonl，`evo watch --json` 就是 tail 这个文件。
  一行：{"schema_version": 1, "id", "ts", "event", "project", "item", "data"}。data 只放能 JSON 的东西；
  状态对象（s、it）放 live，不落盘。

只用标准库。内核文件，不 import 任何功能包。
"""
import json
import os
import sys
import threading
import time

SCHEMA_VERSION = 1
LOG_MAX = 5 * 1024 * 1024          # events.jsonl 超过 5 MB 挪成 .1（只留一份旧的）

# 内核会发的事件（只加不改名；功能包也可以发自己的，名字用「功能包id.xxx」）
EVENTS = {
    "item.created": "新件登记了",
    "build.started": "施工派工",
    "build.done": "施工交卷",
    "verify.started": "验收派工",
    "verify.passed": "验收通过",
    "verify.failed": "验收没过 / 打回",
    "gate.pending": "开了一个等老板点头的闸门",
    "gate.resolved": "闸门结了（通过 / 打回 / 不做…）",
    "item.merged": "件合进主线",
    "push.done": "推到远端",
    "deploy.done": "上线（部署成功）",
    "deploy.failed": "部署失败",
    "item.shipped": "件随批次上线",
    "item.dropped": "件不做了",
    "item.timeline": "件时间线上的其它事（data.kind 是原事件名）",
    "tick.before_dispatch": "一轮里派工之前（同步，功能包可改状态）",
    "tick.after_dispatch": "一轮里派工、推送、查停滞之后（同步，功能包可改状态）",
    "tick.gates": "一轮里读到 Orca 闸门列表之后（同步）",
    "tick.before_save": "一轮里最后存盘之前（同步；live 带 gates，自动收菜在这）",
    "tick": "一轮结束",
    "feature.changed": "功能开关 / 设置变了",
    "feature.error": "某个功能包订阅者出错或超时",
    "watch.ping": "evo watch 的保活（不落盘）",
}


def _now():
    try:
        import evo_time as TM
        return TM.iso()
    except Exception:        # pragma: no cover
        return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Bus:
    def __init__(self, log_path=None, project=None):
        self.log_path = log_path
        self.project = project
        self._subs = []          # (priority, seq, pattern, fn, owner, timeout)
        self._seq = 0
        self.errors = []         # [{owner, event, error}]

    # ---------- 订阅 ----------
    def subscribe(self, pattern, fn, owner="core", priority=50, timeout=30):
        """pattern：完整事件名、"前缀.*" 或 "*"。返回取消订阅的函数。"""
        self._seq += 1
        sub = (priority, self._seq, pattern, fn, owner, timeout)
        self._subs.append(sub)
        self._subs.sort(key=lambda x: (x[0], x[1]))

        def off():
            if sub in self._subs:
                self._subs.remove(sub)
        return off

    def drop_owner(self, owner):
        self._subs = [x for x in self._subs if x[4] != owner]

    def subscribers(self, event=None):
        return [{"owner": x[4], "pattern": x[2], "priority": x[0], "timeout": x[5]}
                for x in self._subs if event is None or _match(x[2], event)]

    # ---------- 发布 ----------
    def publish(self, event, data=None, project=None, item=None, live=None, record=True):
        rec = {"schema_version": SCHEMA_VERSION, "id": f"{time.time_ns()}-{os.getpid()}", "ts": _now(),
               "event": event, "project": project if project is not None else self.project, "item": item,
               "data": _jsonable(data or {})}
        if record:
            self._append(rec)
        ev = dict(rec, live=live or {})
        out = []
        for sub in list(self._subs):
            if _match(sub[2], event):
                out.append(self._call(sub, ev))
        return out

    def _call(self, sub, ev):
        _, _, _, fn, owner, timeout = sub
        if not timeout:
            try:
                return fn(ev)
            except BaseException as e:          # SystemExit 也拦：功能包不能让内核退出
                self._fail(owner, ev, e)
                return None
        box = {}

        def run():
            try:
                box["r"] = fn(ev)
            except BaseException as e:
                box["e"] = e
        t = threading.Thread(target=run, name=f"evo-sub-{owner}", daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            self._fail(owner, ev, TimeoutError(f"超过 {timeout} 秒没处理完"))
            return None
        if "e" in box:
            self._fail(owner, ev, box["e"])
            return None
        return box.get("r")

    def _fail(self, owner, ev, e):
        msg = f"{type(e).__name__}: {e}"[:500]
        self.errors.append({"owner": owner, "event": ev["event"], "error": msg})
        print(f"功能包 {owner} 处理 {ev['event']} 出错（只影响它自己）：{msg}", file=sys.stderr)
        self._append({"schema_version": SCHEMA_VERSION, "id": f"{time.time_ns()}-{os.getpid()}", "ts": _now(),
                      "event": "feature.error", "project": ev.get("project"), "item": ev.get("item"),
                      "data": {"feature": owner, "event": ev["event"], "error": msg}})

    def _append(self, rec):
        p = self.log_path
        if not p:
            return
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if os.path.exists(p) and os.path.getsize(p) > LOG_MAX:
                os.replace(p, p + ".1")
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"事件没写进 events.jsonl：{e}", file=sys.stderr)


def _match(pattern, event):
    if pattern == "*" or pattern == event:
        return True
    return pattern.endswith(".*") and event.startswith(pattern[:-1])


def _jsonable(d):
    try:
        json.dumps(d, ensure_ascii=False)
        return d
    except (TypeError, ValueError):
        return {k: (v if isinstance(v, (str, int, float, bool, type(None), list, dict)) else str(v)) for k, v in d.items()}


# ---------- evo watch：tail events.jsonl ----------
def watch(log_path, out=None, project=None, replay=0, ping=15, stop=None, poll=0.5):
    """把 events.jsonl 新增的行原样（每行一个 JSON）写到 out；project 过滤；replay 先吐最后 N 行；
    每 ping 秒没事件吐一行 watch.ping（不落盘）。stop() 返回真就退出（测试用）。文件被挪走（轮转）会重新打开。"""
    out = out or sys.stdout

    def emit(line):
        out.write(line.rstrip("\n") + "\n")
        out.flush()

    def ok(line):
        if not project:
            return True
        try:
            return json.loads(line).get("project") in (project, None)
        except ValueError:
            return False

    emit(json.dumps({"schema_version": SCHEMA_VERSION, "event": "watch.ping", "ts": _now(), "project": project,
                     "data": {"hello": True, "events": sorted(EVENTS)}}, ensure_ascii=False))
    pos, ino = 0, None
    if os.path.exists(log_path):
        st = os.stat(log_path)
        ino = st.st_ino
        if replay:
            lines = open(log_path, encoding="utf-8", errors="replace").read().splitlines()[-replay:]
            for ln in lines:
                if ln.strip() and ok(ln):
                    emit(ln)
        pos = st.st_size
    last = time.time()
    buf = ""
    while not (stop and stop()):
        try:
            st = os.stat(log_path)
            if ino is not None and st.st_ino != ino or st.st_size < pos:
                pos = 0
            ino = st.st_ino
            if st.st_size > pos:
                with open(log_path, encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    buf += f.read()
                    pos = f.tell()
                *lines, buf = buf.split("\n")
                for ln in lines:
                    if ln.strip() and ok(ln):
                        emit(ln)
                        last = time.time()
        except FileNotFoundError:
            pass
        if ping and time.time() - last >= ping:
            emit(json.dumps({"schema_version": SCHEMA_VERSION, "event": "watch.ping", "ts": _now(), "project": project,
                             "data": {}}, ensure_ascii=False))
            last = time.time()
        time.sleep(poll)
