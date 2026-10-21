"""evo 内核库：岗位卡片的基础（第十八轮从 evo_team 抽出来）。

派工时要用：工人命令怎么填 {model} / {thinking}、卡片是哪个工具、哪个订阅账号、备用怎么展开。
团队 / 模型协调功能包（kit/features/team）在这之上做健康检查、路线、成绩和建议；它关着时派工照样能用这里的。
"""
import os, re, shlex

# 各工具的命令模板（向导用；{model} 为空时连同前面的参数一起去掉）。真机参数名见 docs/model-coordination.md「只能在 Mac mini 上验」。
TOOL_CMDS = {"claude": "claude --model {model}",
             "codex": "codex --model {model} -c model_reasoning_effort={thinking}",
             "dsh": "dsh --model {model}",
             "pi": "pi --model {model} --thinking {thinking}"}

def tool_of(rc):
    rc = rc or {}
    if rc.get("tool"):
        return rc["tool"]
    try:
        return os.path.basename(shlex.split(rc.get("cmd") or "")[0])
    except (IndexError, ValueError):
        return ""


def via_of(rc):
    """模型走 magpie 还是工具自带：显式写 via 就听它的；没写时模型名是 magpie 组（group/…）才算 magpie。"""
    rc = rc or {}
    if rc.get("via") in ("magpie", "cli"):
        return rc["via"]
    return "magpie" if any(str(m).startswith("group/") for m in rc.get("models") or []) else "cli"


def render_cmd(cmd, model, thinking=None):
    """把 {model} / {thinking} 填进命令。值为空时，连同紧挨着的那个参数一起去掉（例如 "--model {model}"）。"""
    out = cmd or ""
    for key, val in (("model", model), ("thinking", thinking)):
        ph = "{" + key + "}"
        if ph not in out:
            continue
        if val:
            out = out.replace(ph, str(val))
        else:
            out = re.sub(r"\s+-{1,2}[\w-]+(=|\s+)\S*" + re.escape(ph) + r"\S*", "", out)
            out = re.sub(r"\s+-c\s+\S*" + re.escape(ph) + r"\S*", "", out)
            out = out.replace(ph, "")
    return out.strip()


def fallback_rc(rc, tools=None):
    """把卡片的备用（fallback）展开成一份能派工的岗位配置。没写 cmd 时：按 tools.<工具>.cmd、内置模板、主命令的顺序找。"""
    fb = (rc or {}).get("fallback") or {}
    if not fb or not (fb.get("models") or fb.get("cmd") or fb.get("tool")):
        return None
    tool = fb.get("tool") or tool_of(rc)
    cmd = fb.get("cmd") or ((tools or {}).get(tool) or {}).get("cmd") or (TOOL_CMDS.get(tool) if fb.get("tool") else None) or rc.get("cmd")
    out = {k: v for k, v in rc.items() if k not in ("fallback", "tool", "via", "models", "thinking", "account", "cmd")}
    out.update({"cmd": cmd, "tool": tool, "models": list(fb.get("models") or []), "thinking": fb.get("thinking", rc.get("thinking"))})
    if fb.get("via"):
        out["via"] = fb["via"]
    if fb.get("account"):
        out["account"] = fb["account"]
    return out


def account_of(rc):
    """订阅账号：显式 account → 工具名 tool → 命令第一个词。同一账号额度一起满。"""
    rc = rc or {}
    return rc.get("account") or rc.get("tool") or tool_of({"cmd": rc.get("cmd")}) or "?"


