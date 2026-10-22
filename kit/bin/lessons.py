#!/usr/bin/env python3
"""evoloop 错题本工具。

  python3 scripts/lessons.py lint      [--file LESSONS.md]   校验条目格式
  python3 scripts/lessons.py verify    [--file LESSONS.md]   校验引用的 sha 真实存在
  python3 scripts/lessons.py promote   [--file LESSONS.md] [--threshold 3]  列出该升级的条目
  python3 scripts/lessons.py stats     [--file LESSONS.md]   概况

只解析「活跃教训」「已关单」两节中以 '### L-' 开头的条目。
关单标准（第二十二轮）：机制上不可能再发生才算关——Mechanism 写 code/test/script/gate/hook/static + 指向；只有 rule/review 的不算关。
"""
import argparse, re, subprocess, sys
from dataclasses import dataclass, field

ENTRY = re.compile(r"^### (L-\d{4}) (.+)$")
FIELD = re.compile(r"^- \*\*(Why|Evidence|Do|Done right|Seen|Category|Mechanism)\*\*:\s*(.*)$")
SEEN = re.compile(r"^(\d+)×\s*\(([^)]*)\)")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
SHA = re.compile(r"`([0-9a-f]{7,40})`")
REQUIRED = ("Why", "Evidence", "Seen", "Category")
# 第二十二轮：关单标准——不是「修了」，而是「机制上不可能再发生」。Mechanism: `<kind> — <指向：路径 / `sha` / #issue>`
# 强弱：代码结构（code/test/script/gate/hook）> 静态检查（static）> 规则/技能（rule）> 靠人审（review）
MECH_STRONG = ("code", "test", "script", "gate", "hook", "static")
MECH_KINDS = MECH_STRONG + ("rule", "review")
MECH = re.compile(r"^([a-z]+)\s*(?:[—–:-]+\s*(.*))?$")
CLOSED = "已关单"


@dataclass
class Lesson:
    id: str
    title: str
    line: int
    fields: dict = field(default_factory=dict)
    closed: bool = False

    @property
    def mechanism(self):
        """(kind, 指向)；没写返回 (None, "")。"""
        m = MECH.match(self.fields.get("Mechanism", "").strip())
        return (m.group(1), (m.group(2) or "").strip()) if m else (None, "")

    @property
    def seen_dates(self):
        return sorted(set(DATE.findall(self.fields.get("Seen", ""))))


def parse(path):
    lessons, cur, section = [], None, ""
    in_comment = False
    for i, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.rstrip("\n")
        if "<!--" in line: in_comment = True
        if in_comment:
            if "-->" in line: in_comment = False
            continue
        if line.startswith("## "):
            section = line[3:].strip(); cur = None; continue
        if section not in ("活跃教训", CLOSED):
            continue
        m = ENTRY.match(line)
        if m:
            cur = Lesson(m.group(1), m.group(2).strip(), i, closed=section == CLOSED); lessons.append(cur); continue
        if line.startswith("### "):     # 分类小标题（### 2. 修一类不修一例）：后面的字段不再算进上一条
            cur = None; continue
        f = FIELD.match(line)
        if f and cur:
            cur.fields[f.group(1)] = f.group(2).strip()
    return lessons


def lint(lessons):
    errs, ids = [], set()
    for l in lessons:
        where = f"line {l.line} {l.id}"
        if l.id in ids: errs.append(f"{where}: duplicate id")
        ids.add(l.id)
        for k in REQUIRED:
            if not l.fields.get(k): errs.append(f"{where}: missing **{k}**")
        s = l.fields.get("Seen", "")
        m = SEEN.match(s)
        if s and not m:
            errs.append(f"{where}: Seen must look like '2× (2026-10-05, 2026-10-07)'")
        elif m and int(m.group(1)) != len(l.seen_dates):
            errs.append(f"{where}: Seen says {m.group(1)}× but lists {len(l.seen_dates)} distinct dates")
        ev = l.fields.get("Evidence", "")
        if ev and not (SHA.search(ev) or re.search(r"#\d+", ev)):
            errs.append(f"{where}: Evidence needs a `sha` or #issue")
        if len(l.title) < 6 or l.title.startswith(("注意", "小心")):
            errs.append(f"{where}: title should be an actionable imperative rule")
        kind, ptr = l.mechanism
        if l.fields.get("Mechanism") and kind not in MECH_KINDS:
            errs.append(f"{where}: **Mechanism** must start with one of {'/'.join(MECH_KINDS)}")
        elif kind in MECH_STRONG and not ptr:
            errs.append(f"{where}: Mechanism {kind} needs a pointer (path, `sha` or #issue)")
        if l.closed and (kind not in MECH_STRONG or not ptr):
            errs.append(f"{where}: closed lessons need a mechanical Mechanism ({'/'.join(MECH_STRONG)} + pointer); "
                        "rule/review only is not closed")
    return errs


def verify(lessons):
    errs = []
    for l in lessons:
        for k in ("Evidence", "Done right"):
            for sha in SHA.findall(l.fields.get(k, "")):
                ok = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                                    capture_output=True).returncode == 0
                if not ok: errs.append(f"line {l.line} {l.id}: {k} sha `{sha}` not found in repo")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["lint", "verify", "promote", "stats"])
    ap.add_argument("--file", default="LESSONS.md")
    ap.add_argument("--threshold", type=int, default=3)
    a = ap.parse_args()
    lessons = parse(a.file)
    if a.cmd == "lint":
        errs = lint(lessons)
    elif a.cmd == "verify":
        errs = verify(lessons)
    elif a.cmd == "promote":
        c = [l for l in lessons if not l.closed and len(l.seen_dates) >= a.threshold]
        for l in c:
            print(f"{l.id} Seen {len(l.seen_dates)}× ({', '.join(l.seen_dates)}): {l.title}")
        if not c: print(f"no lesson seen on ≥{a.threshold} distinct days")
        return 0
    else:
        act = [l for l in lessons if not l.closed]
        cats = {}
        for l in act: cats[l.fields.get("Category", "?")] = cats.get(l.fields.get("Category", "?"), 0) + 1
        print(f"active lessons: {len(act)}" + (f", closed: {len(lessons) - len(act)}" if len(act) != len(lessons) else ""))
        mk = {}
        for l in act: mk[l.mechanism[0] or "none"] = mk.get(l.mechanism[0] or "none", 0) + 1
        print("mechanism: " + ", ".join(f"{k} {v}" for k, v in sorted(mk.items(), key=lambda x: -x[1])))
        print(f"not yet mechanical: {sum(1 for l in act if l.mechanism[0] not in MECH_STRONG)}")
        for k, v in sorted(cats.items(), key=lambda x: -x[1]): print(f"  {k}: {v}")
        near = [l for l in act if len(l.seen_dates) == a.threshold - 1]
        if near: print("one sighting from promotion: " + ", ".join(l.id for l in near))
        return 0
    for e in errs: print("✗", e)
    print(f"{'✓' if not errs else '✗'} {a.cmd}: {len(lessons)} lessons, {len(errs)} problems")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
