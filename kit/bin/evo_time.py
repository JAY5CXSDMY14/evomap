"""evo 的时间工具：现在几点（可用 EVO_NOW 固定，测试用）、时区、时间窗、额度重置时间解析。

只用标准库。时区默认 Asia/Shanghai；系统没有时区库时退回固定 +08:00（上海不实行夏令时，结果一样）。
"""
import datetime as dt
import os
import re
import time

DEFAULT_TZ = "Asia/Shanghai"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
# 内置时间窗。trading:* 另外排除配置里的节假日（windows.holidays）
PRESETS = {
    "trading:cn": "mon-fri 09:30-11:30,13:00-15:00",
    "trading:hk": "mon-fri 09:30-12:00,13:00-16:00",
}


def now():
    """现在（epoch 秒）。EVO_NOW 可写 ISO 时间（带时区）或 epoch，测试和演练用。"""
    v = os.environ.get("EVO_NOW")
    if not v:
        return time.time()
    try:
        return float(v)
    except ValueError:
        return dt.datetime.fromisoformat(v).timestamp()


def tz(name=None):
    name = name or DEFAULT_TZ
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        if name in ("Asia/Shanghai", "Asia/Hong_Kong", "Asia/Taipei", "Asia/Singapore"):
            return dt.timezone(dt.timedelta(hours=8))
        return dt.timezone.utc


def local(ts=None, zone=None):
    return dt.datetime.fromtimestamp(now() if ts is None else ts, tz(zone))


def iso(ts=None, zone=None):
    """ISO 8601 带时区，例 2026-10-20T12:00:00+08:00（手拼，不依赖 isoformat 的实现细节）。"""
    t = local(ts, zone)
    off = t.utcoffset() or dt.timedelta(0)
    mins = int(off.total_seconds() // 60)
    sign = "+" if mins >= 0 else "-"
    return t.strftime("%Y-%m-%dT%H:%M:%S") + f"{sign}{abs(mins) // 60:02d}:{abs(mins) % 60:02d}"


def parse_iso(s):
    """iso() 写出的时间读回 epoch 秒（心跳文件用）。"""
    return dt.datetime.fromisoformat(s).timestamp()


def hm(s):
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def in_range(minute, start, end):
    """minute 是否在 [start, end) 里；end < start 表示跨午夜。start == end 表示空（关闭）。"""
    if start == end:
        return False
    return start <= minute < end if start < end else (minute >= start or minute < end)


# ---------- 时间窗 ----------
def _days(spec):
    out = set()
    for part in spec.split(","):
        part = part.strip().lower()
        if part in ("daily", "*", "every", "all"):
            return set(range(7))
        if part in ("weekdays", "workdays"):
            out |= set(range(5)); continue
        if part == "weekends":
            out |= {5, 6}; continue
        if "-" in part:
            a, b = part.split("-")
            ia, ib = DAYS.index(a[:3]), DAYS.index(b[:3])
            i = ia
            while True:
                out.add(i)
                if i == ib:
                    break
                i = (i + 1) % 7
        else:
            out.add(DAYS.index(part[:3]))
    return out


def parse_window(spec, cfg=None):
    """把窗口写法解析成 [(星期集合, [(起, 止)...]), ...]，外加是否排除节假日。
    写法：预设名（trading:cn）、配置 windows.presets 里的名字，或「mon-fri 09:30-11:30,13:00-15:00」，多段用 ; 隔开。
    写错抛 ValueError。"""
    cfg = cfg or {}
    presets = {**PRESETS, **(cfg.get("presets") or {})}
    holidays = False
    raw = spec.strip()
    if raw in presets:
        holidays = raw.startswith("trading:") or bool((cfg.get("holiday_presets") or []) and raw in cfg["holiday_presets"])
        raw = presets[raw]
    if raw.endswith("!holidays"):
        holidays = True; raw = raw[: -len("!holidays")].strip()
    groups = []
    for g in raw.split(";"):
        g = g.strip()
        if not g:
            continue
        m = re.fullmatch(r"([a-z,\-*]+)\s+([\d:,\-\s]+)", g, re.I)
        if not m:
            raise ValueError(f"看不懂的时间窗：{g!r}（例：mon-fri 09:30-11:30,13:00-15:00 或 trading:cn）")
        try:
            days = _days(m.group(1))
            ranges = []
            for r in m.group(2).split(","):
                a, b = r.strip().split("-")
                ranges.append((hm(a), hm(b)))
        except (ValueError, IndexError):
            raise ValueError(f"看不懂的时间窗：{g!r}（例：mon-fri 09:30-11:30,13:00-15:00 或 trading:cn）")
        groups.append((days, ranges))
    if not groups:
        raise ValueError(f"时间窗是空的：{spec!r}")
    return groups, holidays


def window_open(spec, cfg=None, ts=None):
    """现在是否在时间窗内。cfg 是全局配置里的 windows 段：tz、holidays、presets。"""
    cfg = cfg or {}
    groups, use_hol = parse_window(spec, cfg)
    t = local(ts, cfg.get("tz"))
    if use_hol and t.strftime("%Y-%m-%d") in set(cfg.get("holidays") or []):
        return False
    minute = t.hour * 60 + t.minute
    for days, ranges in groups:
        for a, b in ranges:
            if b < a:   # 跨午夜：属于起始那天
                if (t.weekday() in days and minute >= a) or ((t.weekday() - 1) % 7 in days and minute < b):
                    return True
            elif t.weekday() in days and a <= minute < b:
                return True
    return False


# ---------- 订阅额度用完 ----------
RATE_PATTERNS = [
    r"\brate[ _-]?limit(ed|s)?\b", r"\busage limit\b", r"limit (has been )?reached", r"hit your (usage )?limit",
    r"quota (exceeded|exhausted)", r"too many requests", r"\b429\b.{0,40}(too many|rate|limit|error|retry)",
    r"(error|status|http)\D{0,20}\b429\b", r"try again (at|in)\b", r"limit will reset", r"resets? (at|in)\b",
    r"额度(已)?用(完|尽)", r"请求过于频繁",
]
_RATE_RE = re.compile("|".join(f"(?:{p})" for p in RATE_PATTERNS), re.I)
# 10-23 Air：上游 / 网关故障（magpie 转发的 5xx、proxyconn、auth_unavailable、TLS 超时）不是额度用完。
# 这类行只有在同一行里明说 429 / quota / usage limit / rate limit 时才算额度；否则归「上游故障」。
UPSTREAM_PATTERNS = [
    r"API Error:\s*5\d\d\b", r"\b50[234]\b.{0,60}(gateway|unavailable|timeout|proxy)", r"proxyconn",
    r"auth_unavailable", r"no auth available", r"TLS handshake timeout", r"connection (refused|reset)",
    r"ECONNRESET|ECONNREFUSED|ETIMEDOUT", r"bad gateway", r"service unavailable",
]
_UP_RE = re.compile("|".join(f"(?:{p})" for p in UPSTREAM_PATTERNS), re.I)
_STRONG_RATE_RE = re.compile(r"\b429\b|quota (exceeded|exhausted)|usage limit|rate[ _-]?limit|额度(已)?用(完|尽)|too many requests", re.I)


def is_upstream(line):
    """这一行是上游 / 网关故障（而且没明说额度）。"""
    return bool(line) and bool(_UP_RE.search(line)) and not _STRONG_RATE_RE.search(line)


def upstream_line(text, tail=60):
    """在最后 tail 行里找上游故障提示，返回那一行（没有返回 None）。"""
    if not text:
        return None
    for l in reversed([l for l in str(text).splitlines() if l.strip()][-tail:]):
        if is_upstream(l):
            return l.strip()[:300]
    return None


def rate_limit_line(text, tail=60):
    """在最后 tail 行里找订阅额度/限流提示，返回命中的那一行（没有返回 None）。只看尾部，免得把很早的旧提示当成现在。"""
    if not text:
        return None
    lines = [l for l in str(text).splitlines() if l.strip()][-tail:]
    for l in reversed(lines):
        if _RATE_RE.search(l) and not is_upstream(l):
            return l.strip()[:300]
    return None


_UNITS = {"d": 86400, "day": 86400, "h": 3600, "hr": 3600, "hour": 3600, "m": 60, "min": 60, "minute": 60, "s": 1, "sec": 1, "second": 1}
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def parse_reset(text, base=None, zone=None):
    """从额度提示里解析重置时间（epoch 秒）。认得：
      in 2 hours / in 1h 20m / in 2 days 3 hours 10 minutes
      at 3:05 PM / at 15:05 / at 5pm (Asia/Shanghai)
      at 2026-10-21 04:00 / at Oct 21st, 2026 5:04 AM
      Claude Code 老格式「...|1760000000」
    解析不出返回 None（调用方默认 60 分钟）。"""
    if not text:
        return None
    base = now() if base is None else base
    s = str(text)
    m = re.search(r"\|(\d{10})\b", s)
    if m:
        return float(m.group(1))
    m = re.search(r"\bin\s+((?:\d+\s*(?:days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b[\s,and]*)+)", s, re.I)
    if m:
        total = 0
        for n, u in re.findall(r"(\d+)\s*([a-z]+)", m.group(1), re.I):
            u = u.lower().rstrip("s") if len(u) > 1 else u.lower()
            total += int(n) * _UNITS.get(u, _UNITS.get(u[:1], 60))
        if total:
            return base + total
    zm = re.search(r"\(([A-Za-z]+/[A-Za-z_]+)\)", s)
    z = tz(zm.group(1) if zm else zone)
    ref = dt.datetime.fromtimestamp(base, z)
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)[ T](\d{1,2}):(\d\d)", s)
    if m:
        y, mo, d, h, mi = map(int, m.groups())
        return dt.datetime(y, mo, d, h, mi, tzinfo=z).timestamp()
    m = re.search(r"\b(" + "|".join(_MONTHS) + r")[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(20\d\d)?,?\s+(?:at\s+)?(\d{1,2})(?::(\d\d))?\s*([ap]\.?m\.?)?", s, re.I)
    if m:
        mo = _MONTHS.index(m.group(1)[:3].lower()) + 1
        y = int(m.group(3) or ref.year); h = int(m.group(4)); mi = int(m.group(5) or 0)
        h = _ampm(h, m.group(6))
        return dt.datetime(y, mo, int(m.group(2)), h, mi, tzinfo=z).timestamp()
    m = re.search(r"\b(?:at|until|after)\s+(\d{1,2})(?::(\d\d))?\s*([ap]\.?m\.?)?(?![\d-])", s, re.I)
    if m and (m.group(2) or m.group(3)):
        h = _ampm(int(m.group(1)), m.group(3)); mi = int(m.group(2) or 0)
        t = ref.replace(hour=h % 24, minute=mi, second=0, microsecond=0)
        if t.timestamp() <= base:
            t += dt.timedelta(days=1)
        return t.timestamp()
    return None


def _ampm(h, ap):
    if not ap:
        return h
    ap = ap.lower().replace(".", "")
    if ap == "pm" and h < 12:
        return h + 12
    if ap == "am" and h == 12:
        return 0
    return h
