"""测试夹具：每个测试一套独立的 HOME、假 Orca、临时 git 仓库和裸远端。

evo 整个以子进程方式跑（和常驻进程一样），PATH 最前面是 tests/fakes（orca、gh、curl 都是假的）。
"""
import glob, json, os, shutil, subprocess, sys

import pytest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVO = os.path.join(KIT, "bin", "evo")
FAKES = os.path.join(KIT, "tests", "fakes")
WORKER = os.path.join(FAKES, "worker.py")


def sh(*cmd, cwd=None, env=None, check=True):
    r = subprocess.run(list(cmd), cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f"{cmd} 失败：{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


class Loop:
    def __init__(self, tmp):
        self.tmp = str(tmp)
        self.root = os.path.join(self.tmp, "evo")
        self.projects = os.path.join(self.root, "projects")
        self.orca_dir = os.path.join(self.tmp, "orca")
        home = os.path.join(self.tmp, "home")
        for d in (self.projects, self.orca_dir, home):
            os.makedirs(d, exist_ok=True)
        base = {k: v for k, v in os.environ.items() if not k.startswith(("EVO_", "TUBU_", "GIT_"))}
        self.env = {**base, "PATH": FAKES + os.pathsep + base.get("PATH", ""), "HOME": home, "EVO_HOME": self.projects,
                    "FAKE_ORCA_DIR": self.orca_dir, "TMPDIR": self.tmp, "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                    "EVO_TG_TOKEN": "tok", "EVO_TG_CHAT": "chat", "PYTHONDONTWRITEBYTECODE": "1",
                    # 不联网：HTTP / 邮件记到假目录；时间固定在周二中午（免打扰、时间窗、额度暂停都按它算）
                    "EVO_FAKE_NET": self.orca_dir, "EVO_NOW": "2026-10-20T12:00:00+08:00"}
        self.write_global({})

    # ---------- 配置 ----------
    def write_global(self, extra):
        py = sys.executable
        g = {"limits": {"builders_total": 2, "owner_queue_pause": 5, "rework_rounds": 2, "stall_minutes": 15},
             "roles": {"build": {"cmd": f"{py} {WORKER} build", "models": ["model-a", "model-b"], "prompt": "roles/builder.md",
                                 "boot_seconds": 0},
                       "verify": {"cmd": f"{py} {WORKER} verify", "models": ["model-a", "model-b"], "prompt": "roles/verifier.md",
                                  "boot_seconds": 0},
                       "retro": {"prompt": "roles/retro.md"}},
             "notify": {"macos": False},
             "auto_ship_gate": False}          # 自动收菜默认关：只在专门的测试里打开，免得影响别的测试
        for k, v in extra.items():
            g[k] = {**g[k], **v} if isinstance(v, dict) and isinstance(g.get(k), dict) else v
        json.dump(g, open(os.path.join(self.root, "config.json"), "w"), ensure_ascii=False)

    def cfg_path(self, code):
        return os.path.join(self.projects, code, "config.json")

    def patch_cfg(self, code, **kv):
        c = json.load(open(self.cfg_path(code)))
        c.update(kv)
        json.dump(c, open(self.cfg_path(code), "w"), ensure_ascii=False)

    # ---------- 仓库 ----------
    def repo(self, code):
        return os.path.join(self.tmp, "repos", code, "work")

    def remote(self, code):
        return os.path.join(self.tmp, "repos", code, "remote.git")

    def git(self, cwd, *a, check=True):
        return sh("git", "-C", cwd, *a, env=self.env, check=check)

    def project(self, code, test_cmd=None, push=True, **cfg):
        repo, remote = self.repo(code), self.remote(code)
        os.makedirs(repo)
        self.git(repo, "init", "-q", "-b", "main")
        open(os.path.join(repo, "README.md"), "w").write(f"# {code}\n")
        self.git(repo, "add", "README.md"); self.git(repo, "commit", "-qm", "init")
        if push:
            sh("git", "init", "-q", "--bare", "-b", "main", remote, env=self.env)
            self.git(repo, "remote", "add", "origin", remote)
            self.git(repo, "push", "-q", "origin", "main")
        if test_cmd is None:
            test_cmd = f"echo ran >> {self.tmp}/tests-{code}.log"
        r = self.evo("import", code, "--name", f"项目{code}", "--path", repo, "--test", test_cmd)
        assert "就绪" in r.stdout, r.stdout + r.stderr
        if cfg:
            self.patch_cfg(code, **cfg)
        return repo

    def remote_head(self, code):
        return self.git(self.remote(code), "rev-parse", "main")

    def remote_files(self, code):
        return self.git(self.remote(code), "ls-tree", "-r", "--name-only", "main").splitlines()

    def test_runs(self, code):
        p = os.path.join(self.tmp, f"tests-{code}.log")
        return len(open(p).read().splitlines()) if os.path.exists(p) else 0

    # ---------- evo ----------
    def evo(self, *args, check=False, timeout=120):
        return subprocess.run([sys.executable, EVO, *args], env=self.env, capture_output=True, text=True, timeout=timeout)

    def ok(self, *args):
        r = self.evo(*args)
        assert r.returncode == 0, f"evo {args} 退出码 {r.returncode}\n{r.stdout}\n{r.stderr}"
        return r

    def tick(self, code):
        return self.ok("-p", code, "tick")

    def add(self, code, title="修复注册页验证码不刷新", scope="web/", extra=()):
        return self.ok("-p", code, "add", "--kind", "fix", "--title", title, "--scope", scope, *extra)

    def state(self, code):
        return json.load(open(os.path.join(self.projects, code, "state", "state.json"), encoding="utf-8"))

    def item(self, code, key=None):
        items = self.state(code)["items"]
        return items[key] if key else next(iter(items.values()))

    def run_until(self, code, pred, n=8):
        for _ in range(n):
            self.tick(code)
            if pred(self.state(code)):
                return self.state(code)
        raise AssertionError(f"{n} 轮后条件仍不满足：{json.dumps(self.state(code), ensure_ascii=False)[:1500]}")

    def status_json(self, code):
        return json.loads(self.ok("-p", code, "status", "--json").stdout)

    # ---------- 假 Orca / 工人 / 提醒 ----------
    def plan(self, **roles):
        json.dump(roles, open(os.path.join(self.orca_dir, "plan.json"), "w"))

    def orca_state(self):
        return json.load(open(os.path.join(self.orca_dir, "state.json")))

    def workers(self):
        p = os.path.join(self.orca_dir, "workers.log")
        return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []

    def _read(self, *parts):
        p = os.path.join(*parts)
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

    def notifications(self):
        """所有提醒事件（outbox 一事件一行，不管推没推）。真正推出去的看 telegram_sent() / mails()。"""
        return self._read(self.orca_dir, "curl.log") + self._read(self.root, "outbox.jsonl")

    def outbox(self):
        return [json.loads(l) for l in self._read(self.root, "outbox.jsonl").splitlines() if l.strip()]

    def http_log(self):
        return [json.loads(l) for l in self._read(self.orca_dir, "http.log").splitlines() if l.strip()]

    def telegram_sent(self):
        """真正发到 Telegram 的消息（sendMessage 的 body）。"""
        return [json.loads(r["body"]) for r in self.http_log() if r["url"].endswith("/sendMessage")]

    def mails(self):
        return [json.loads(l) for l in self._read(self.orca_dir, "mail.log").splitlines() if l.strip()]

    def http_responses(self, mapping):
        json.dump(mapping, open(os.path.join(self.orca_dir, "http_responses.json"), "w"), ensure_ascii=False)


def state_is(st, key=None):
    return lambda s: (s["items"][key] if key else next(iter(s["items"].values())))["state"] == st


@pytest.fixture
def loop(tmp_path):
    return Loop(tmp_path)
