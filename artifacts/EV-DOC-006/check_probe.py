#!/usr/bin/env python3
"""EV-DOC-006 自检：notes/r20-rework.md 必须第一行是「返工探针」、末行是「已返工」。

只读，不改仓库。退出码 0 = 通过；1 = 不通过（逐条打印原因）。
第一轮验收要求是「写一行『返工探针』」，第一版因此只允许一行；
返工按验收原因「在文件末尾加一行『已返工』」放宽为：第一行「返工探针」，末行「已返工」。
中间不允许多余空行，首尾不带空白，行尾换行可有可无（文本文件惯例）。
"""
import pathlib
import sys

# 可选参数：指定别的文件（用于反证脚本本身能判 fail）
TARGET = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (
    pathlib.Path(__file__).resolve().parents[2] / "notes" / "r20-rework.md"
)
FIRST = "返工探针"
LAST = "已返工"

if not TARGET.exists():
    print(f"FAIL 文件不存在: {TARGET}")
    sys.exit(1)

data = TARGET.read_bytes()
lines = data.decode("utf-8").splitlines()
print(f"path   : {TARGET}")
print(f"bytes  : {len(data)}")
print(f"hex    : {data.hex()}")
print(f"lines  : {lines!r}")
print(f"expect : 第一行「{FIRST}」，末行「{LAST}」")

reasons = []
if not lines:
    reasons.append("文件是空的")
else:
    if len(lines) < 2:
        reasons.append(f"只有 {len(lines)} 行，末行缺少「{LAST}」")
    elif len(lines) > 2:
        reasons.append(f"行数不是 2，而是 {len(lines)}（中间不允许多余行）")
    for idx, expect in ((0, FIRST), (-1, LAST)):
        got = lines[idx]
        if got == expect:
            continue
        if got.strip() == expect:
            reasons.append(f"第 {idx} 行行首/行尾多了空白: {got!r}")
        else:
            reasons.append(f"第 {idx} 行应是「{expect}」，实际是 {got!r}")

if reasons:
    for r in reasons:
        print(f"FAIL {r}")
    sys.exit(1)

print(f"PASS 第一行是「{FIRST}」，末行是「{LAST}」")
sys.exit(0)
