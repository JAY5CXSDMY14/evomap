import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import evo_roles as R


def test_dsh_template_is_headless_oneshot():
    assert R.TOOL_CMDS["dsh"].startswith("dsh --profile headless")
    assert R.is_oneshot({"cmd": "dsh --profile headless -"})
    assert not R.is_oneshot({"cmd": "claude --model x"})


def test_launch_failed_detects_air_cases():
    air = "u@MacBook-Air ev-feat-001 % dsh --model group/free-ds\nerror: --profile <name> is required\nu@MacBook-Air ev-feat-001 %"
    assert R.launch_failed(air)
    silent = "u@MacBook-Air ev-feat-001 % dsh --model group/free-ds\nu@MacBook-Air ev-feat-001 %"
    assert R.launch_failed(silent)
    fed = "zsh: no such file or directory: 任务号\nzsh: command not found: 4.\nbquote>"
    assert R.launch_failed(fed)


def test_launch_ok_cases():
    assert R.launch_failed("") is None
    assert R.launch_failed("u@Air ev % claude --model m\n╭───╮\n│ ✻ Welcome to Claude Code │") is None
