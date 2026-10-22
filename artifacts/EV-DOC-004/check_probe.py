#!/usr/bin/env python3
"""EV-DOC-004 自检：notes/r20-probe.md 的内容必须正好是「第二轮」。

只读，不改仓库。退出码 0 = 通过；1 = 不通过（逐条打印原因）。
「正好」按字节比：多一个换行、多一个空格、BOM 都算 fail。
"""
import pathlib
import sys

# 可选参数：指定别的文件（用于反证脚本本身能判 fail）
TARGET = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else (
    pathlib.Path(__file__).resolve().parents[2] / "notes" / "r20-probe.md"
)
EXPECTED = "第二轮".encode("utf-8")

if not TARGET.exists():
    print(f"FAIL 文件不存在: {TARGET}")
    sys.exit(1)

data = TARGET.read_bytes()
print(f"path   : {TARGET}")
print(f"bytes  : {len(data)}")
print(f"hex    : {data.hex()}")
print(f"text   : {data.decode('utf-8', 'replace')!r}")
print(f"expect : {EXPECTED!r} ({len(EXPECTED)} bytes)")

if data == EXPECTED:
    print("PASS 内容正好是「第二轮」")
    sys.exit(0)

if data.rstrip() == EXPECTED:
    print(f"FAIL 内容多了尾部空白: {data[len(EXPECTED):]!r}")
elif EXPECTED in data:
    print("FAIL 内容包含「第二轮」但不等于它")
else:
    print("FAIL 内容不是「第二轮」")
sys.exit(1)
