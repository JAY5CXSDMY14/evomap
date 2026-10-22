#!/usr/bin/env python3
"""EV-DOC-003 自检：README 的相对链接是否存在、新增小节是否在末尾、指向的文档是否存在。

只读，不改仓库。退出码 0 = 全部通过；1 = 有 MISS（逐条打印）。

本任务的施工分支基线早于 docs/multica.md 的提交，所以该文档在本分支上按设计不存在。
传 --upstream-clone <路径> 时，脚本会去那个「已经跟上真实远端」的克隆里核对：
它的 HEAD 是否等于 `git ls-remote origin main`，以及目标文件是否真的在里面。
两者都成立，就把这条链接记作 UPSTREAM（合并到 main 后生效），不算 MISS。
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = os.path.join(ROOT, "README.md")

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIX = ("http://", "https://", "#", "mailto:")


def rel_links(text):
    out = []
    for m in LINK.finditer(text):
        target = m.group(1).strip().split("#")[0]
        if not target or target.startswith(SKIP_PREFIX):
            continue
        out.append(target)
    return out


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def upstream_status(clone, path):
    """这个克隆是不是真的跟上了远端 main，以及 path 在不在里面。

    返回 ("current"|"stale"|"absent"|"error", 说明)。
    """
    if not clone:
        return "error", "没给 --upstream-clone，无法核对本分支基线里还没有的文件"
    # 工作区里的 .git 是文件而不是目录，所以用 rev-parse 判断是不是 git 仓库
    if git(["rev-parse", "--git-dir"], clone).returncode != 0:
        return "error", "%s 不是 git 仓库" % clone
    remote = git(["ls-remote", "origin", "main"], clone)
    if remote.returncode != 0:
        return "error", "拿不到 origin main（可能没网或没权限）: %s" % remote.stderr.strip()[:120]
    want = remote.stdout.split()[0] if remote.stdout.split() else ""
    head = git(["rev-parse", "HEAD"], clone).stdout.strip()
    if not want:
        return "error", "origin main 返回空"
    if head != want:
        return "stale", "该克隆 HEAD %s 不等于远端 main %s，不能拿它作证" % (head[:8], want[:8])
    if git(["cat-file", "-e", "HEAD:" + path], clone).returncode == 0:
        return "current", "在远端 main %s 上存在" % want[:8]
    return "absent", "远端 main %s 上也没有" % want[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream-clone", default="",
                    help="一个已跟上远端 main 的克隆，用来核对本分支基线里还没有的文件")
    args = ap.parse_args()

    with open(README, encoding="utf-8") as f:
        text = f.read()

    links = rel_links(text)
    print("相对链接数: %d" % len(links))
    miss = []
    upstream = []
    for target in links:
        if os.path.exists(os.path.join(ROOT, target)):
            print("  OK       %s" % target)
            continue
        state, why = upstream_status(args.upstream_clone, target)
        if state == "current":
            print("  UPSTREAM %s（本分支基线里没有；%s，合并到 main 后生效）" % (target, why))
            upstream.append(target)
        elif state in ("stale", "absent"):
            print("  MISS     %s（%s）" % (target, why))
            miss.append(target)
        else:
            print("  MISS     %s（%s）" % (target, why))
            miss.append(target)

    has_section = "\n## Multica 执行端\n" in text
    print("新增小节存在: %s" % has_section)
    tail_ok = text.rstrip().endswith("见 [docs/multica.md](docs/multica.md)。")
    print("新增小节在文件末尾: %s" % tail_ok)
    mentions = all(k in text for k in ("Multica", "排期", "闸门", "上限", "docs/multica.md"))
    print("内容含 排期/闸门/上限 与 docs/multica.md 指向: %s" % mentions)

    ok = not miss and has_section and tail_ok and mentions
    print("结论: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
