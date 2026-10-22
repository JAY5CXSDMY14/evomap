"""evo 的派工后端（第二十轮，设计见 docs/multica-backend.md）。

evo 是大脑（排队、闸门、返工上限、找老板、上线）；执行端只负责「派人干活、看到干到哪」。
两种执行端，项目配置 executor 选：
  orca     —— 老路：Orca 终端 + orchestration 任务 / 闸门 / 收件箱（OrcaExecutor，行为和第十九轮完全一样）
  multica  —— 新路：一件 = 一个 Multica issue，施工 / 验收 / 决策是三个固定 agent（MulticaExecutor）

接口分两层：
  1. 设计稿 §4 的七个动作：ensure_project / create / assign / poll / comment / close / health。
  2. evo 内核原来直接拿 Orca 用的「编排」原语：任务（带依赖）、闸门、收件箱、工作区、工人终端。
     Orca 后端原样转给 orca CLI；Multica 后端在 evo 自己的账本（state/exec-multica.json）里记任务和闸门，
     收件箱由轮询 issue 合成（run 结束 → worker_done）。所以内核的返工上限、决策批次、闸门逻辑一行不用改。
"""
import json, os, re, shlex, time


class ExecError(SystemExit):
    """执行端出错：和第十七轮起 orca(...) 的约定一样，转成 SystemExit，由调用方按「这一条出错」隔离。"""


class Executor:
    """执行端接口。内核只通过它派工、收回报。"""
    name = "?"
    label = "?"            # 给人看的名字（日志、推送）
    worker_noun = "工人终端"

    def __init__(self, k):
        self.k = k         # 内核（evo 的全局名字：run_cmd、tmo、CFG、STATE_DIR……）

    # ---- 设计稿 §4 的七个动作 ----
    def ensure_project(self, s=None):
        raise NotImplementedError

    def create(self, kind, title, spec):
        raise NotImplementedError

    def assign(self, task, role):
        raise NotImplementedError

    def poll(self, task):
        """→ {state, report, branch, last_activity}"""
        raise NotImplementedError

    def comment(self, task, text):
        raise NotImplementedError

    def close(self, task, ok=True):
        raise NotImplementedError

    def health(self):
        """→ (通不通, 不通的原因)"""
        raise NotImplementedError

    # ---- 内核用的编排原语（Orca 时代的语义）----
    def compat(self, *args, ok=True):
        """功能包里旧的 K.orca(...) 调用走这里（只认 orchestration 的任务 / 闸门子集）。"""
        raise NotImplementedError

    def coord(self, s):
        raise NotImplementedError

    def task_list(self, c):
        raise NotImplementedError

    def task_create(self, c, title, spec, deps=None):
        raise NotImplementedError

    def task_update(self, c, tid, status, result=None, ok=False):
        raise NotImplementedError

    def gate_create(self, c, task, question, options):
        raise NotImplementedError

    def gate_list(self, c):
        """→ 闸门列表；读不到返回 None。"""
        raise NotImplementedError

    def gate_resolve(self, c, gid, resolution):
        """→ (成没成, 错误)"""
        raise NotImplementedError

    def worktree_create(self, repo, name):
        raise NotImplementedError

    def worktree_rm(self, path):
        raise NotImplementedError

    def terminal_alive(self, h):
        raise NotImplementedError

    def terminal_close(self, h):
        raise NotImplementedError

    def terminal_read(self, h):
        raise NotImplementedError

    def launch(self, c, path, title, rc, model, tid, role=None, key=None, it=None):
        """开工：→ (工人句柄, 派工号)"""
        raise NotImplementedError

    def inbox(self, c, s=None):
        """收回报：→ (消息列表, 确认号, 原始结果)"""
        raise NotImplementedError

    def inbox_ack(self, c, did):
        raise NotImplementedError

    def worker_gone(self, did):
        """这次派工的工人还在不在：True = 不在了。读不到算在。"""
        raise NotImplementedError

    def repo_add(self, path, timeout):
        """登记仓库：→ 'ok' / 'fail' / 'missing'（没装命令）"""
        return "ok"

    def on_delivery(self, s, k, it, role, m):
        """收到这件这一岗的回报、交内核处理之前（Multica：把施工分支 / 工作目录记进件里）。"""
        return None

    def link(self, h):
        """面板上「打开」用的地址（没有返回 None）。"""
        return None


# ======================================================================================
# Orca：第十九轮之前散在 evo 里的约 40 处 orca(...) 原样收进来，行为不变
# ======================================================================================
class OrcaExecutor(Executor):
    name = "orca"
    label = "Orca"
    worker_noun = "Orca 终端"

    def __init__(self, k, cmd):
        super().__init__(k)
        self.cmd = list(cmd)

    def cli(self, *args, ok=True):
        k = self.k
        r = k.run_cmd(self.cmd + list(args) + ["--json"], timeout=k.tmo("orca"), extra_env=False)   # 第十七轮：超时 / 没装都转成 SystemExit，不让进程直接崩
        if r.returncode in (124, 127):
            raise ExecError(f"orca {' '.join(args[:2])} {'超时' if r.returncode == 124 else '跑不起来'}：{r.stderr.strip()[-200:]}")
        try:
            j = json.loads(r.stdout)
        except Exception:
            raise ExecError(f"orca {' '.join(args[:2])} 输出无法解析: {r.stdout[:200]} {r.stderr[:200]}")
        if ok and not j.get("ok"):
            raise ExecError(f"orca {' '.join(args[:2])} 失败: {j.get('error')}")
        return j.get("result") or {}, j

    compat = cli

    # ---- 七个动作（Orca 版：薄包装）----
    def ensure_project(self, s=None):
        return self.coord(s) if s is not None else None

    def health(self):
        k = self.k
        r = k.run_cmd(self.cmd + ["status", "--json"], timeout=k.tmo("orca"), extra_env=False)
        try:
            j = json.loads(r.stdout or "{}")
        except Exception:
            j = {}
        reach = _find_key(j, "reachable")
        up = r.returncode == 0 and reach is not False and (reach is True or j.get("ok") is True)
        if up:
            return True, ""
        return False, ("没装 orca 命令" if r.returncode == 127 else ("orca status 超时" if r.returncode == 124 else "Orca 应用没在运行"))

    def comment(self, task, text):
        return None              # Orca 没有「给工人留言」的命令（见 docs/orca-rehearsal.md）

    def close(self, task, ok=True):
        return None              # Orca 时代合并 / 不做后只关终端（cleanup 里做），任务本身没有「关」这一步

    # ---- 编排原语 ----
    def coord(self, s):
        """统筹终端：接棒器自己在 Orca 里的身份。"""
        if s["coord"]:
            res, j = self.cli("terminal", "show", "--terminal", s["coord"], ok=False)
            if j.get("ok"):
                return s["coord"]
        res, _ = self.cli("terminal", "create", "--worktree", f"path:{self.k.CFG['repo']}", "--title", "evo-coordinator")
        s["coord"] = res["terminal"]["handle"]
        self.cli("orchestration", "run-create", "--from", s["coord"], "--objective", "evo autopilot")
        return s["coord"]

    def task_list(self, c):
        res, _ = self.cli("orchestration", "task-list", "--from", c)
        return {t["id"]: t for t in res.get("tasks", [])}

    def task_create(self, c, title, spec, deps=None):
        t, _ = self.cli("orchestration", "task-create", "--from", c, "--task-title", title, "--spec", spec,
                        *(["--deps", json.dumps(deps)] if deps else []))
        return t["task"]["id"]

    def task_update(self, c, tid, status, result=None, ok=False):
        self.cli("orchestration", "task-update", "--from", c, "--id", tid, "--status", status,
                 *(["--result", result] if result is not None else []), ok=ok)

    def gate_create(self, c, task, question, options):
        g, _ = self.cli("orchestration", "gate-create", "--from", c, "--task", task, "--question", question,
                        "--options", json.dumps(options))
        return g["gate"]["id"]

    def gate_list(self, c):
        gl, j = self.cli("orchestration", "gate-list", "--from", c, ok=False)
        return gl.get("gates", []) if j.get("ok") else None

    def gate_resolve(self, c, gid, resolution):
        _, j = self.cli("orchestration", "gate-resolve", "--from", c, "--id", gid, "--resolution", resolution, ok=False)
        return bool(j.get("ok")), j.get("error")

    def worktree_create(self, repo, name):
        res, _ = self.cli("worktree", "create", "--repo", f"path:{repo}", "--name", name)
        return res["worktree"]["path"]

    def worktree_rm(self, path):
        self.cli("worktree", "rm", "--worktree", f"path:{path}", ok=False)

    def terminal_alive(self, h):
        _, j = self.cli("terminal", "show", "--terminal", h, ok=False)
        return bool(j.get("ok")), j.get("error")

    def terminal_close(self, h):
        self.cli("terminal", "close", "--terminal", h, ok=False)

    def terminal_read(self, h):
        """读工人终端最近的输出（orca terminal read）；读不到返回空串。"""
        r, j = self.cli("terminal", "read", "--terminal", h, ok=False)
        if not j.get("ok"):
            return ""
        t = r.get("text") or r.get("output") or r.get("content") or ""
        if not t and isinstance(r.get("lines"), list):
            t = "\n".join(x if isinstance(x, str) else (x.get("text") or "") for x in r["lines"])
        return t if isinstance(t, str) else ""

    def launch_check(self, h, title, cmd):
        """Air 试跑 10-21：dsh --model 直接报错退回 shell，evo 却记成派工成功、还把任务书逐行喂给 zsh。"""
        bad = self.k.R.launch_failed(self.terminal_read(h))
        if bad:
            self.terminal_close(h)
            raise ExecError(f"工人命令没跑起来（{title}：{cmd}）。终端最后几行：\n{bad[-600:]}")

    def launch(self, c, path, title, rc, model, tid, role=None, key=None, it=None):
        """开终端、起工人命令、派工。返回 (终端句柄, 派工号)。"""
        k = self.k; R = k.R
        res, _ = self.cli("terminal", "create", "--worktree", f"path:{path}", "--title", title)
        h = res["terminal"]["handle"]
        base = rc["cmd"]
        if R.tool_of(rc) == "dsh" and re.match(r"^dsh\s+--model\b", base):
            base = R.TOOL_CMDS["dsh"]              # 旧配置里的「dsh --model {model}」跑不起来（dsh 没有 --model），按新写法改
            print(f"岗位命令 {rc['cmd']} 是旧写法，改用 {base}（模型以 DSH 里设置的为准）")
        cmd = R.render_cmd(base, k.model_alias(model), rc.get("thinking"))      # {model} / {thinking}；空值连参数一起去掉；第十八轮：按本机前缀改名
        print(f"开工人终端 {title} → {h}：{cmd}")
        if R.tool_of(rc) == "claude":
            k.claude_trust(path)                   # Air 试跑 10-21：新工作区里 claude 停在「信任这个文件夹吗」上没人点
        if R.is_oneshot(rc):
            # 一次性工具（dsh headless）：先建派工、拿任务书，写成文件，再「命令 < 文件」启动；不往 shell 里打任务书
            d, _ = self.cli("orchestration", "dispatch", "--from", c, "--task", tid, "--to", h)
            pre, _ = self.cli("orchestration", "dispatch-show", "--from", c, "--task", tid, "--preamble", ok=False)
            text = (pre.get("preamble") or "").replace("ctx_preview", d["dispatch"]["id"])
            pdir = os.path.join(k.STATE_DIR, "prompts"); os.makedirs(pdir, exist_ok=True)
            pf = os.path.join(pdir, f"{title}.md")
            with open(pf, "w", encoding="utf-8") as f:
                f.write(text)
            self.cli("terminal", "send", "--terminal", h, "--text", f"{cmd} < {shlex.quote(pf)}", "--enter", ok=False)
            time.sleep(rc.get("boot_seconds", 3))
            self.launch_check(h, title, cmd)
            return h, d["dispatch"]["id"]
        self.cli("terminal", "send", "--terminal", h, "--text", cmd, "--enter", ok=False)
        time.sleep(rc.get("boot_seconds", 3))
        self.launch_check(h, title, cmd)           # 先确认工人命令真的起来了，再派工；不然任务书会被当成 shell 命令执行
        # 第二十轮注：10-21~22 决策岗连续 5 次 45 分钟超时，根因就是这里 —— --inject 派给卡在 Claude 引导页的终端被拒。
        # Multica 后端没有「往已有终端注入」这一步，改成 issue assign（见 MulticaExecutor.launch）。
        d, j = self.cli("orchestration", "dispatch", "--from", c, "--task", tid, "--to", h, "--inject", ok=False)
        if not j.get("ok"):
            if (j.get("error") or {}).get("code") != "inject_rejected":
                raise ExecError(f"派工失败: {j.get('error')}")
            # 不在 Orca 识别名单里的命令行（自定义包装）：普通派工，再把说明打进终端
            d, _ = self.cli("orchestration", "dispatch", "--from", c, "--task", tid, "--to", h)
            pre, _ = self.cli("orchestration", "dispatch-show", "--from", c, "--task", tid, "--preamble")
            text = (pre.get("preamble") or "").replace("ctx_preview", d["dispatch"]["id"])
            self.cli("terminal", "send", "--terminal", h, "--text", text, "--enter")
        alive, err = self.terminal_alive(h)        # Air 试跑 10-21：evo 记了「已派工」，Orca 里却没有这个终端
        if not alive:
            raise ExecError(f"工人终端 {title}（{h}）派工后就不在了：{err}")
        return h, d["dispatch"]["id"]

    def inbox(self, c, s=None):
        res, _ = self.cli("orchestration", "check", "--terminal", c, "--types", "worker_done,escalation,question,heartbeat", ok=False)
        did = res.get("deliveryId") or res.get("delivery_id") or (res.get("delivery") or {}).get("id")
        return res.get("messages") or [], did, res

    def inbox_ack(self, c, did):
        self.cli("orchestration", "check", "--terminal", c, "--ack", did, ok=False)

    def worker_gone(self, did):
        r, _ = self.cli("orchestration", "worker-show", "--dispatch", did, ok=False)
        obs = (r.get("observation") or {}).get("status")
        return bool((r.get("terminal") or {}).get("orphaned") or (obs and obs != "live"))

    def repo_add(self, path, timeout):
        r = self.k.run_cmd(self.cmd + ["repo", "add", "--path", path, "--json"], timeout=timeout, extra_env=False)
        if r.returncode == 127:
            return "missing"
        return "ok" if '"ok":true' in (r.stdout or "").replace(" ", "") else "fail"


def _find_key(o, key):
    if isinstance(o, dict):
        if key in o:
            return o[key]
        for v in o.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def make(k, cfg):
    """按项目配置选执行端。"""
    return OrcaExecutor(k, shlex.split(cfg.get("orca", "orca")))
