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

    def alive_at(self, did):
        """第二十轮补：执行端看到这次派工最后一次「还在干活」的时间（epoch 秒）；看不到返回 0。"""
        return 0

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


# ======================================================================================
# Multica：一件 = 一个 issue；派工 = issue assign（不再往已有终端 --inject，10-22 决策岗超时的根因就此绕开）
# ======================================================================================
MULTICA_AGENTS = {"build": "施工-DSH", "verify": "验收-Claude", "decide": "决策-Claude"}
def _newest_mtime(path, cap=3000):
    """工作区里最新一次改动的时间（跳过 .git / node_modules；最多看 cap 个文件）。没有工作区返回 None。"""
    if not path or not os.path.isdir(path):
        return None
    best, n = 0.0, 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [x for x in dirs if x not in (".git", "node_modules", ".venv", "__pycache__")]
        for f in files:
            try:
                best = max(best, os.stat(os.path.join(root, f)).st_mtime)
            except OSError:
                pass
            n += 1
            if n >= cap:
                return best
    return best


RUN_ACTIVE = ("queued", "dispatched", "running", "waiting_local_directory", "pending", "claimed", "started")
RUN_OK = ("completed", "succeeded", "success", "done", "finished")
ROLE_NAMES = {"build": "施工", "verify": "验收", "decide": "决策"}
REPOLL_SECONDS = float(os.environ.get("EVO_MULTICA_REPOLL", 300))

BUILD_TAIL = """

---
【交卷方式（Multica）】做完把改动提交到本 issue 的工作分支（不要推送、不要合并到 main）。
最后一条评论里放施工报告：一个 ```json 块，格式同 templates/report.schema.json
（status / summary / changes / tests / unfinished / risks / manual_checks）。
这里不用 orca orchestration send；evo 读你最后的评论。卡住要人回答时把 issue 状态改成 blocked，并在评论里写清问题。"""
VERIFY_TAIL = """

---
【交卷方式（Multica）】你是验收，只读不改。最后一条评论里放 ```json {{"verdict": "pass" 或 "fail", "reasons": ["…"]}}。
施工分支：{branch}；evo 的验收副本（只读）：{wt}"""
DECIDE_TAIL = """

---
【交卷方式（Multica）】只做技术决定，不改任何文件。决定写在最后一条评论的 ```json 块里（{"decisions": [...]}，格式见上面岗位规则）。"""


def _arr(j, *keys):
    """multica 的 list 输出有时是顶层数组，有时包一层 {issues: [...]}。"""
    if isinstance(j, list):
        return j
    if isinstance(j, dict):
        for k in keys:
            if isinstance(j.get(k), list):
                return j[k]
    return []


class MulticaExecutor(Executor):
    name = "multica"
    label = "Multica"
    worker_noun = "Multica issue"

    def __init__(self, k, mcfg, code=None):
        super().__init__(k)
        mcfg = mcfg or {}
        self.cmd = shlex.split(str(mcfg.get("cmd") or "multica"))
        self.project = str(mcfg.get("project") or code or "")
        self.agents = {**MULTICA_AGENTS, **{r: a for r, a in (mcfg.get("agents") or {}).items() if a}}
        self.app_url = str(mcfg.get("app_url") or "").rstrip("/")
        self.workspace = str(mcfg.get("workspace") or os.environ.get("MULTICA_WORKSPACE_SLUG") or "").strip("/")
        # 10-22 Air：网页路由带 workspace slug（/evo/issues/EVO-13），不带会 307 到 /login
        self.issue_url = str(mcfg.get("issue_url") or ("{app_url}/{workspace}/issues/{identifier}" if self.workspace
                                                        else "{app_url}/issues/{identifier}"))

    # ---------- CLI ----------
    def cli(self, *args, ok=True, stdin=None, out=True):
        """跑一条 multica 命令，要 JSON。超时 limits.timeouts.multica（分钟）。ok=False 时失败返回 None。"""
        k = self.k
        cmd = self.cmd + [str(a) for a in args] + (["--output", "json"] if out else [])
        r = k.run_cmd(cmd, timeout=k.tmo("multica"), extra_env=False, input=stdin)
        what = " ".join(str(a) for a in args[:2])
        if r.returncode:
            why = {124: "超时", 127: "跑不起来（没装 multica？）", 2: "连不上服务端", 3: "登录失效（multica login --token）",
                   4: "找不到"}.get(r.returncode, f"退出码 {r.returncode}")
            if ok:
                raise ExecError(f"multica {what} {why}：{(r.stderr or r.stdout).strip()[-200:]}")
            return None
        try:
            return json.loads(r.stdout) if (r.stdout or "").strip() else {}
        except ValueError:
            if ok:
                raise ExecError(f"multica {what} 输出无法解析: {r.stdout[:200]}")
            return None

    # ---------- evo 自己的账本（任务 / 闸门 / 派工），和 Orca 自己的状态一样不进 state.json ----------
    def _lp(self):
        return os.path.join(self.k.STATE_DIR, "exec-multica.json")

    def _load(self):
        try:
            return json.load(open(self._lp(), encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"n": 0, "tasks": {}, "gates": {}, "dispatches": {}, "issues": {}, "agent_ids": {}, "project_id": None}

    def _save(self, L):
        os.makedirs(os.path.dirname(self._lp()), exist_ok=True)
        tmp = self._lp() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(L, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self._lp())

    def _nid(self, L, p):
        L["n"] = L.get("n", 0) + 1
        return f"{p}_{L['n']}"

    # ---------- 七个动作 ----------
    def ensure_project(self, s=None):
        L = self._load()
        if L.get("project_id"):
            return L["project_id"]
        if not self.project:
            raise ExecError("没配 multica.project：项目配置里写 \"multica\": {\"project\": \"<Multica 里的项目名>\"}")
        for p in _arr(self.cli("project", "list"), "projects", "items"):
            if self.project in (p.get("id"), p.get("title"), p.get("name")):
                L["project_id"] = p.get("id"); self._save(L)
                return L["project_id"]
        raise ExecError(f"Multica 里没有项目「{self.project}」：先在 Multica 建好并绑定本地目录（--type local_directory），"
                        f"或改项目配置 multica.project")

    def agent_id(self, role, L=None, refresh=False):
        L = L or self._load()
        name = self.agents.get(role)
        if name in L.get("agent_ids", {}) and not refresh:
            return L["agent_ids"][name]
        j = self.cli("agent", "list", ok=False)
        ids = {a.get("name"): a.get("id") for a in _arr(j, "agents", "items") if isinstance(a, dict)}
        if ids:
            L["agent_ids"] = ids; self._save(L)
        return ids.get(name)

    def create(self, kind, title, spec):
        pid = self.ensure_project()
        # --allow-duplicate：evo 自己保证一件一个 issue；崩溃重来时宁可多一个，也不要被「已有同名 issue」卡死
        j = self.cli("issue", "create", "--title", title[:200], "--project", pid, "--allow-duplicate", "--description-stdin", stdin=spec)
        iss = j.get("issue") if isinstance(j.get("issue"), dict) else j
        ident = iss.get("identifier") or iss.get("id")
        if not ident:
            raise ExecError(f"multica issue create 没返回 issue 号：{json.dumps(j, ensure_ascii=False)[:200]}")
        return ident

    def assign(self, task, role, start=True):
        self.cli("issue", "assign", task, "--to", self.agents[role], *([] if start else ["--no-start"]))

    def comment(self, task, text):
        self.cli("issue", "comment", "add", task, "--content-stdin", stdin=text)

    def close(self, task, ok=True):
        if task:
            self.cli("issue", "status", task, "done" if ok else "cancelled", "--no-start", ok=False)

    def runs(self, task):
        return [r for r in _arr(self.cli("issue", "runs", task, ok=False), "runs", "items") if isinstance(r, dict)]

    def comments(self, task):
        return [c for c in _arr(self.cli("issue", "comment", "list", task, "--full", ok=False), "comments", "items") if isinstance(c, dict)]

    def poll(self, task, since_runs=(), agent_id=None, since_comments=()):
        """→ {state, report, branch, last_activity, run, work_dir}。只看 since_runs 之后、这个 agent 的 run。"""
        iss = self.cli("issue", "get", task, ok=False) or {}
        runs = [r for r in self.runs(task) if r.get("id") not in since_runs and (not agent_id or r.get("agent_id") in (None, agent_id))]
        runs.sort(key=lambda r: str(r.get("created_at") or ""))
        run = runs[-1] if runs else None
        out = {"state": iss.get("status"), "assignee": iss.get("assignee_id"), "last_activity": iss.get("last_activity_at"),
               "run": run, "branch": (run or {}).get("branch_name"), "work_dir": (run or {}).get("work_dir"), "report": None}
        if run and str(run.get("status") or "").lower() not in RUN_ACTIVE:
            cs = self.comments(task)
            mine = [c for c in cs if c.get("source_task_id") == run.get("id")]
            if not mine:
                mine = [c for c in cs if c.get("id") not in since_comments and c.get("author_type") == "agent"
                        and (not agent_id or c.get("author_id") == agent_id)]
            out["report"] = "\n\n".join(str(c.get("content") or "") for c in mine)
        return out

    def health(self):
        k = self.k
        r = k.run_cmd(self.cmd + ["daemon", "status", "--output", "json"], timeout=k.tmo("multica"), extra_env=False)
        if r.returncode == 127:
            return False, "没装 multica 命令"
        if r.returncode == 124:
            return False, "multica daemon status 超时"
        try:
            j = json.loads(r.stdout or "{}")
        except ValueError:
            j = {}
        st = str(_find_key(j, "status") or _find_key(j, "state") or "").lower()
        running = _find_key(j, "running")
        if r.returncode or running is False or st in ("stopped", "not_running", "offline", "dead", "exited"):
            return False, "multica daemon 没在运行"
        a = k.run_cmd(self.cmd + ["agent", "list", "--output", "json"], timeout=k.tmo("multica"), extra_env=False)
        if a.returncode:
            return False, {2: "Multica 服务端连不上", 3: "Multica 登录失效（multica login --token）", 124: "multica agent list 超时"}.get(
                a.returncode, f"multica agent list 失败（{a.returncode}）")
        return True, ""

    # ---------- 编排原语：任务 / 闸门在 evo 自己的账本里，语义同 Orca ----------
    def compat(self, *args, ok=True):
        sub = args[1] if len(args) > 1 and args[0] == "orchestration" else None
        o, i = {}, 2
        while i < len(args):
            if str(args[i]).startswith("--") and i + 1 < len(args) and not str(args[i + 1]).startswith("--"):
                o[args[i][2:]] = args[i + 1]; i += 2
            else:
                i += 1
        c = o.get("from") or o.get("terminal") or "multica"
        if sub == "task-create":
            tid = self.task_create(c, o["task-title"], o.get("spec", ""), json.loads(o.get("deps") or "[]"))
            return {"task": {"id": tid}}, {"ok": True}
        if sub == "task-update":
            self.task_update(c, o["id"], o["status"], o.get("result"))
            return {}, {"ok": True}
        if sub == "task-list":
            return {"tasks": list(self.task_list(c).values())}, {"ok": True}
        if sub == "gate-create":
            gid = self.gate_create(c, o["task"], o["question"], json.loads(o.get("options") or "[]"))
            return {"gate": {"id": gid}}, {"ok": True}
        if sub == "gate-list":
            return {"gates": self.gate_list(c) or []}, {"ok": True}
        if sub == "gate-resolve":
            okr, err = self.gate_resolve(c, o["id"], o["resolution"])
            if ok and not okr:
                raise ExecError(f"闸门 gate-resolve 失败: {err}")
            return {}, {"ok": okr, "error": err}
        raise ExecError(f"Multica 后端不支持 orca {' '.join(map(str, args[:2]))}")

    def coord(self, s):
        self.ensure_project(s)
        s["coord"] = f"multica:{self.project}"
        return s["coord"]

    def _status(self, L, t):
        if t["status"] in ("dispatched", "completed", "failed"):
            return t["status"]
        if any(g["task"] == t["id"] and g["status"] == "pending" for g in L["gates"].values()):
            return "blocked"
        return "ready" if all(L["tasks"].get(d, {}).get("status") == "completed" for d in t["deps"]) else "pending"

    def task_list(self, c):
        L = self._load()
        return {t["id"]: {"id": t["id"], "title": t["title"], "status": self._status(L, t), "deps": json.dumps(t["deps"])}
                for t in L["tasks"].values()}

    def task_create(self, c, title, spec, deps=None):
        L = self._load()
        tid = self._nid(L, "mt")
        L["tasks"][tid] = {"id": tid, "title": title, "spec": spec, "deps": list(deps or []), "status": "pending"}
        self._save(L)
        return tid

    def task_update(self, c, tid, status, result=None, ok=False):
        L = self._load()
        t = L["tasks"].get(tid)
        if not t:
            if ok:
                raise ExecError(f"没有任务 {tid}")
            return
        t["status"] = status
        if result is not None:
            t["result"] = result
        self._save(L)
        if status == "failed" and t.get("role") == "decide" and t.get("issue"):
            self.close(t["issue"], ok=False)            # 决策岗超时：这一批的 issue 作废，下一批另开

    def gate_create(self, c, task, question, options):
        L = self._load()
        gid = self._nid(L, "mg")
        L["gates"][gid] = {"id": gid, "task": task, "question": question, "options": list(options), "status": "pending", "resolution": None}
        self._save(L)
        return gid

    def gate_list(self, c):
        return list(self._load()["gates"].values())

    def gate_resolve(self, c, gid, resolution):
        L = self._load()
        g = L["gates"].get(gid)
        if not g or g["status"] != "pending":
            return False, {"code": "gate_not_pending"}
        g["status"] = "resolved"; g["resolution"] = resolution
        self._save(L)
        return True, None

    def worktree_create(self, repo, name):
        return None              # Multica 自己开工作区；evo 的验收 / 合并副本在交卷时从施工分支取（on_delivery）

    def worktree_rm(self, path):
        k = self.k
        own = os.path.join(k.STATE_DIR, "worktrees")
        if path and os.path.abspath(path).startswith(os.path.abspath(own) + os.sep):
            k.run_cmd(["git", "-C", k.CFG["repo"], "worktree", "remove", "--force", path], timeout=k.tmo("git"))

    def terminal_alive(self, h):
        return True, None

    def terminal_close(self, h):
        return None              # issue 留着：返工 / 验收还派到同一个 issue 上；合并或不做时由 close() 收尾

    def terminal_read(self, h):
        return self._load().get("issues", {}).get(h, {}).get("tail", "")

    def launch(self, c, path, title, rc, model, tid, role=None, key=None, it=None):
        """派工 = issue assign。施工第一次建 issue；返工 / 验收在同一个 issue 上追加评论再 assign；决策批次每批一个新 issue。"""
        L = self._load()
        role = role or ("verify" if title.endswith("-verify") else "decide" if title.endswith("-decide") else "build")
        t = L["tasks"].get(tid) or {"spec": ""}
        spec = t.get("spec", "")
        ex = (it or {}).get("exec") or {}
        issue = ex.get("issue") if role != "decide" and ex.get("backend") == "multica" else None
        aid = self.agent_id(role, L)
        if not issue:
            ttl = (t.get("title") or title) if role == "decide" else f"{key} {(it or {}).get('title', '')}".strip()
            issue = self.create(role, ttl, spec + (DECIDE_TAIL if role == "decide" else BUILD_TAIL if role == "build" else ""))
            before_runs, before_comments = [], []
            if role == "verify":       # 少见：验收时还没有 issue（老状态迁过来）
                self.comment(issue, VERIFY_TAIL.format(branch=ex.get("branch") or "?", wt=(it or {}).get("worktree") or "?"))
            self.assign(issue, role)
        else:
            old_runs = self.runs(issue)
            for r in old_runs:      # 10-22 Air：返工时旧 run 还在跑，新 run 只能排在它后面，旧 run 交的卷也没人收。先停掉旧的
                if str(r.get("status") or "").lower() in RUN_ACTIVE and r.get("id"):
                    self.cli("issue", "cancel-task", r["id"], "--issue", issue, ok=False)
                    print(f"停掉 {issue} 上还在跑的旧 run {str(r['id'])[:8]}（换人 / 返工前）")
            before_runs = [r.get("id") for r in old_runs]
            body = spec + (VERIFY_TAIL.format(branch=ex.get("branch") or "?", wt=(it or {}).get("worktree") or "?")
                           if role == "verify" else BUILD_TAIL)
            self.assign(issue, role, start=False)       # 先换人（不起 run），再留言：留言本身会叫醒被指派的 agent
            self.comment(issue, f"【evo · {ROLE_NAMES.get(role, role)}：{title}】\n\n" + body)
            before_comments = [x.get("id") for x in self.comments(issue)]
            if not [r for r in self.runs(issue) if r.get("id") not in before_runs]:
                self.cli("issue", "rerun", issue, ok=False)   # 留言没叫醒（工作区设置不同）：显式重跑一次
        did = self._nid(L, "md")
        L = {**self._load(), "n": L["n"]}
        L["dispatches"][did] = {"id": did, "task": tid, "issue": issue, "role": role, "agent": self.agents.get(role), "agent_id": aid,
                                "at": time.time(), "runs_before": before_runs, "comments_before": before_comments, "done": False}
        if tid in L["tasks"]:
            L["tasks"][tid].update(status="dispatched", issue=issue, role=role)
        self._save(L)
        if it is not None:
            it["exec"] = {**ex, "backend": "multica", "issue": issue, "agent": self.agents.get(role)}
        print(f"派给 Multica：{issue} → {self.agents.get(role)}（{title}）")
        return issue, did

    def inbox(self, c, s=None):
        """收回报：每个没交卷的派工看一眼它的 issue。先用一次 issue list（只取几个字段）筛出有动静的，再细看 run 和评论。"""
        try:
            pid = self.ensure_project()
        except SystemExit:
            pid = None
        L = self._load()
        open_d = [d for d in L["dispatches"].values() if not d.get("done")]
        if not open_d:
            return [], None, {}
        acts = {}
        try:
            j = None if not pid else self.cli("issue", "list", "--project", pid, "--limit", "100",
                         "--fields", "id,identifier,status,assignee_id,last_activity_at", ok=False)
            for x in _arr(j, "issues", "items"):
                acts[x.get("identifier")] = x; acts[x.get("id")] = x
        except SystemExit:
            pass
        msgs, batch = [], []
        for d in open_d:
            x = acts.get(d["issue"])
            if x and d.get("seen") == x.get("last_activity_at") and d.get("polled") and time.time() - d.get("polled_at", 0) < REPOLL_SECONDS:
                continue             # 没动静：不细看（run 失败可能不留评论、不改活动时间，所以每 5 分钟至少细看一次）
            p = self.poll(d["issue"], d.get("runs_before") or (), d.get("agent_id"), d.get("comments_before") or ())
            d["polled"] = True; d["polled_at"] = time.time(); d["seen"] = (x or {}).get("last_activity_at") or p.get("last_activity")
            run = p.get("run") or {}
            rs = str(run.get("status") or "").lower()
            tail = "\n".join(str(v) for v in (run.get("error"), p.get("report")) if v)
            L.setdefault("issues", {})[d["issue"]] = {"tail": tail[-4000:], "state": p.get("state")}
            gone = p.get("state") == "cancelled" or (p.get("assignee") and d.get("agent_id") and p["assignee"] != d["agent_id"])
            d["gone"] = bool(gone and not run)
            if p.get("state") == "blocked" and d["role"] != "decide":
                typ, outcome = "question", None
            elif not run or rs in RUN_ACTIVE:
                if run:
                    self._heartbeat(d, run, x)
                continue
            else:
                typ, outcome = "worker_done", "succeeded" if rs in RUN_OK else "failed"
            body = p.get("report") or (run.get("error") or "")
            if d["role"] == "verify" and typ == "worker_done" and outcome == "succeeded":
                outcome = "succeeded" if verdict(body) else "failed"
            d["outcome"] = outcome
            msgs.append({"id": f"mx:{d['id']}", "type": typ, "task_id": d["task"], "subject": f"{d['role']} {outcome}" if outcome else None,
                         "body": body, "payload": {"outcome": outcome, "taskId": d["task"]},
                         "exec": {"issue": d["issue"], "branch": p.get("branch"), "work_dir": p.get("work_dir"), "run": run.get("id")}})
            batch.append(d["id"])
        if batch:
            L["pending_ack"] = sorted(set(L.get("pending_ack") or []) | set(batch))
        self._save(L)
        return msgs, ("mx-ack" if batch else None), {"messages": msgs}

    def inbox_ack(self, c, did):
        """evo 处理完这批回报：派工标交卷，任务标完成 / 失败（同 Orca 的 worker_done 语义），决策批次的 issue 收尾。"""
        L = self._load()
        for x in L.pop("pending_ack", None) or []:
            d = L["dispatches"].get(x)
            if not d or d.get("done"):
                continue
            d["done"] = True
            t = L["tasks"].get(d["task"])
            if t and t["status"] == "dispatched" and d.get("outcome"):      # 提问（blocked）不改任务状态，同 Orca 的 question
                t["status"] = "completed" if d["outcome"] == "succeeded" else "failed"
            if d["role"] == "decide":
                self.close(d["issue"], ok=True)
        self._save(L)

    def worker_gone(self, did):
        return bool(self._load()["dispatches"].get(did, {}).get("gone"))

    def alive_at(self, did):
        return float(self._load()["dispatches"].get(did, {}).get("alive_at") or 0)

    def _heartbeat(self, d, run, x):
        """10-22 Air：dsh 跑了 19 分钟、调了 97 次工具，evo 却判「15 分钟没有任何回报」——run 在跑时 issue 不留评论、
        状态不变。这里用「run 的 usage / 尝试次数 + issue 活动时间 + 工作区最新改动时间」做指纹，指纹变了就算还在干活。"""
        sig = json.dumps([run.get("usage"), run.get("attempt"), run.get("status"), (x or {}).get("last_activity_at"),
                          _newest_mtime(run.get("work_dir"))], sort_keys=True, default=str)
        if d.get("hb_sig") != sig:
            d["hb_sig"] = sig
        # 10-22 Air 第二次：dsh 用 job_output 干等 28 分钟的 pytest，期间指纹一点不变，又被判卡住。
        # Multica 的 run 只要还是活跃状态就算活着（agent 真死了 daemon 会把 run 标 failed）；兜圈子交给 run_max_minutes。
        d["alive_at"] = time.time()

    def repo_add(self, path, timeout):
        return "skip"

    def on_delivery(self, s, k, it, role, m):
        """施工交卷：把施工分支取进 evo 自己的克隆（分支 evo/<件号>，工作区 state/worktrees/<件号>），验收和合并都在这份上做。"""
        ex = m.get("exec") or {}
        e = it.setdefault("exec", {"backend": "multica", "issue": None, "agent": None, "branch": None})
        e.update({x: ex[x] for x in ("issue", "branch") if ex.get(x)})
        if role != "build" or m.get("type") != "worker_done" or (m.get("payload") or {}).get("outcome") != "succeeded":
            return
        K = self.k; repo = K.CFG["repo"]; wd, br = ex.get("work_dir"), ex.get("branch")
        if wd and os.path.isdir(wd):
            dirty = K.run_cmd(["git", "-C", wd, "status", "--porcelain", "--untracked-files=no"], timeout=K.tmo("git")).stdout.strip()
            if dirty:                  # 和 Orca 时代一样：说交付了但还有没提交的改动 → 当施工失败，按返工走
                m["payload"]["outcome"] = "failed"
                m["body"] = (m.get("body") or "") + "\n施工说交付了，但工作区还有没提交的改动：" + dirty[:120]
                return
        mine = f"evo/{k.lower()}"
        src = None                     # 先取进一个不是分支的引用（分支 evo/<件号> 可能正签出在 evo 的验收副本里，git 不让直接写）
        if wd and br and os.path.isdir(wd):
            ref = f"refs/evo/fetch/{k.lower()}"
            if K.run_cmd(["git", "-C", repo, "fetch", "-q", wd, f"+{br}:{ref}"], timeout=K.tmo("git_net")).returncode == 0:
                src = ref
        if not src and br and K.run_cmd(["git", "-C", repo, "rev-parse", "--verify", "-q", br], timeout=K.tmo("git")).returncode == 0:
            src = br                   # 工作目录不在了，但分支就在 evo 的克隆里（项目绑定的就是这份克隆）
        if not src:
            m["payload"]["outcome"] = "failed"
            m["body"] = (m.get("body") or "") + f"\n找不到施工分支（{br or '没报分支'}，工作目录 {wd or '?'}）：evo 取不到改动"
            return
        wt = os.path.join(K.STATE_DIR, "worktrees", k.lower())
        if os.path.isdir(wt):
            r = K.run_cmd(["git", "-C", wt, "checkout", "-q", "-f", "-B", mine, src], timeout=K.tmo("git"))
        else:
            os.makedirs(os.path.dirname(wt), exist_ok=True)
            K.run_cmd(["git", "-C", repo, "branch", "-f", mine, src], timeout=K.tmo("git"))
            r = K.run_cmd(["git", "-C", repo, "worktree", "add", "-q", wt, mine], timeout=K.tmo("git"))
        if r.returncode:
            m["payload"]["outcome"] = "failed"
            m["body"] = (m.get("body") or "") + f"\nevo 开验收副本失败：{r.stderr.strip()[-200:]}"
            return
        it["worktree"] = wt

    def link(self, h):
        if not (h and self.app_url):
            return None
        return self.issue_url.format(app_url=self.app_url, identifier=h, project=self.project, workspace=self.workspace)


def verdict(body):
    """验收结论：```json {"verdict": "pass"|"fail"}``` 优先；没有就认「验收通过 / 不通过」字样；都没有算不通过。"""
    for raw in reversed(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", body or "", re.S)):
        try:
            j = json.loads(raw)
        except ValueError:
            continue
        v = str(j.get("verdict") or j.get("result") or j.get("outcome") or "").lower()
        if v in ("pass", "passed", "ok", "succeeded", "通过"):
            return True
        if v in ("fail", "failed", "reject", "不通过", "打回"):
            return False
    t = body or ""
    if re.search(r"验收不通过|不通过|打回|\bFAIL", t):
        return False
    return bool(re.search(r"验收通过|\bPASS", t))


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


def backend_of(cfg):
    """项目用哪个执行端：配置 executor（multica | orca）；没写 = orca（老项目保持原样，新项目 evo new / import 时写 multica）。"""
    v = str((cfg or {}).get("executor") or "orca").strip().lower()
    return v if v in ("orca", "multica") else "orca"


def make(k, cfg):
    """按项目配置选执行端。"""
    if backend_of(cfg) == "multica":
        return MulticaExecutor(k, cfg.get("multica") or {}, cfg.get("code"))
    return OrcaExecutor(k, shlex.split(cfg.get("orca", "orca")))
