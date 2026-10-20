#!/usr/bin/env python3
"""evoloop 错题本工具。

  python3 scripts/lessons.py lint      [--file LESSONS.md]   校验条目格式
  python3 scripts/lessons.py verify    [--file LESSONS.md]   校验引用的 sha 真实存在
  python3 scripts/lessons.py promote   [--file LESSONS.md] [--threshold 3]  列出该升级的条目
  python3 scripts/lessons.py stats     [--file LESSONS.md]   概况

只解析「活跃教训」一节中以 '### L-' 开头的条目。
"""
import argparse, re, subprocess, sys
from dataclasses import dataclass, field

ENTRY = re.compile(r"^### (L-\d{4}) (.+)$")
FIELD = re.compile(r"^- \*\*(Why|Evidence|Do|Done right|Seen|Category)\*\*:\s*(.*)$")
SEEN = re.compile(r"^(\d+)×\s*\(([^)]*)\)")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
SHA = re.compile(r"`([0-9a-f]{7,40})`")
REQUIRED = ("Why", "Evidence", "Seen", "Category")


@dataclass
class Lesson:
    id: str
    title: str
    line: int
    fields: dict = field(default_factory=dict)

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
        if section != "活跃教训":
            continue
        m = ENTRY.match(line)
        if m:
            cur = Lesson(m.group(1), m.group(2).strip(), i); lessons.append(cur); continue
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
        c = [l for l in lessons if len(l.seen_dates) >= a.threshold]
        for l in c:
            print(f"{l.id} Seen {len(l.seen_dates)}× ({', '.join(l.seen_dates)}): {l.title}")
        if not c: print(f"no lesson seen on ≥{a.threshold} distinct days")
        return 0
    else:
        cats = {}
        for l in lessons: cats[l.fields.get("Category", "?")] = cats.get(l.fields.get("Category", "?"), 0) + 1
        print(f"active lessons: {len(lessons)}")
        for k, v in sorted(cats.items(), key=lambda x: -x[1]): print(f"  {k}: {v}")
        near = [l for l in lessons if len(l.seen_dates) == a.threshold - 1]
        if near: print("one sighting from promotion: " + ", ".join(l.id for l in near))
        return 0
    for e in errs: print("✗", e)
    print(f"{'✓' if not errs else '✗'} {a.cmd}: {len(lessons)} lessons, {len(errs)} problems")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
