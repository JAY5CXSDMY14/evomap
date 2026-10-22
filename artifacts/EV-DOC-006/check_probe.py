#!/usr/bin/env python3
"""EV-DOC-006 自检：notes/r20-rework.md 必须存在，且第一行正好是「返工探针」。

只读，不改仓库。退出码 0 = 通过；1 = 不通过（逐条打印原因）。
本轮验收要求是「写一行『返工探针』」，所以按行比：文件必须恰好一行，内容正好四个字，
不带尾部空格；行尾换行可有可无（文本文件惯例）。
"""
import pathlib
import sys

# 可选参数：指定别的文件（用于反证脚本本身能判 fail）
TARGET = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (
    pathlib.Path(__file__).resolve().parents[2] / "notes" / "r20-rework.md"
)
EXPECTED = "返工探针"

if not TARGET.exists():
    print(f"FAIL 文件不存在: {TARGET}")
    sys.exit(1)

data = TARGET.read_bytes()
lines = data.decode("utf-8").splitlines()
print(f"path   : {TARGET}")
print(f"bytes  : {len(data)}")
print(f"hex    : {data.hex()}")
print(f"lines  : {lines!r}")
print(f"expect : 1 行，内容正好是「{EXPECTED}」")

reasons = []
if len(lines) != 1:
    reasons.append(f"行数不是 1，而是 {len(lines)}")
elif lines[0] != EXPECTED:
    if lines[0].strip() == EXPECTED:
        reasons.append(f"行首/行尾多了空白: {lines[0]!r}")
    elif EXPECTED in lines[0]:
        reasons.append("这一行包含「返工探针」但不等于它")
    else:
        reasons.append(f"这一行不是「返工探针」，而是 {lines[0]!r}")

if reasons:
    for r in reasons:
        print(f"FAIL {r}")
    sys.exit(1)

print("PASS 文件有一行，内容正好是「返工探针」")
sys.exit(0)
