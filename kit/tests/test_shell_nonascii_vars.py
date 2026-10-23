"""macOS 自带 bash 3.2 在某些 locale 下会把紧跟变量名的中文字节当成变量名的一部分（Air 10-23：RTSRC（ → unbound variable）。
所有 shell 脚本里 $VAR 后面紧跟非 ASCII 字符时必须写成 ${VAR}。"""
import pathlib, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
BAD = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7F]")


def test_no_bare_var_before_nonascii():
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.sh"], capture_output=True, text=True).stdout.split()
    hits = []
    for f in files:
        for n, line in enumerate((ROOT / f).read_text(encoding="utf-8").splitlines(), 1):
            if BAD.search(line):
                hits.append(f"{f}:{n}")
    assert not hits, "变量后紧跟中文要写 ${VAR}：" + ", ".join(hits)
