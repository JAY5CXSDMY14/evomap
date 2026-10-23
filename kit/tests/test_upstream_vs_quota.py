"""10-23 Air：magpie 上游 5xx / proxyconn / auth_unavailable 不算额度；终端里的 evo 读常驻 plist 里的 TG 配置。"""
import os, plistlib, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import evo_time as TM


def test_upstream_lines_are_not_quota():
    for l in ['API Error: 504 Post "https://api.artbloom.tech/v1/messages?beta=true": proxyconn',
              "API Error: 503 auth_unavailable: no auth available (providers=openai-compatible-opencode-go, model=deepseek-flash; last",
              'Post "https://api.github.com/graphql": net/http: TLS handshake timeout']:
        assert TM.rate_limit_line("x\n" + l) is None
        assert TM.upstream_line("x\n" + l)


def test_explicit_429_still_quota():
    l = "API Error: 503 no auth available (last error: 429 rate limit, try again in 2 hours)"
    assert TM.rate_limit_line(l)
    assert not TM.is_upstream(l)


def test_tg_env_from_launchd_plist(tmp_path, monkeypatch):
    la = tmp_path / "Library" / "LaunchAgents"; la.mkdir(parents=True)
    with open(la / "com.evoloop.autopilot.plist", "wb") as f:
        plistlib.dump({"EnvironmentVariables": {"EVO_TG_TOKEN": "t1", "EVO_TG_CHAT": "c1"}}, f)
    monkeypatch.setenv("HOME", str(tmp_path))
    for k in ("EVO_TG_TOKEN", "EVO_TG_CHAT", "TUBU_TG_TOKEN", "TUBU_TG_CHAT"):
        monkeypatch.delenv(k, raising=False)
    import evo_notify as N
    N._LAUNCHD_ENV = None
    assert N.env("EVO_TG_TOKEN") == "t1" and N.env("TUBU_TG_CHAT") == "c1"
    N._LAUNCHD_ENV = None
