"""订阅额度暂停、用量计数与异常、时间窗、决策岗批量叫醒、施工报失败。"""
import datetime as dt, json, os, sys

import pytest

from conftest import KIT, state_is

sys.path.insert(0, os.path.join(KIT, "bin"))
import evo_time as TM  # noqa: E402

SH = dt.timezone(dt.timedelta(hours=8))


def ts(s):
    return dt.datetime.fromisoformat(s).timestamp()


# ---------- 解析：额度提示 ----------
@pytest.mark.parametrize("text,expect", [
    ("Claude usage limit reached. Your limit will reset at 5pm (Asia/Shanghai).", "2026-10-20T17:00:00+08:00"),
    ("You've hit your usage limit. Try again in 2 hours 30 minutes.", "2026-10-20T14:30:00+08:00"),
    ("rate limited, try again in 1h 20m", "2026-10-20T13:20:00+08:00"),
    ("usage limit: try again in 2 days", "2026-10-22T12:00:00+08:00"),
    ("Rate limit reached. Try again at 3:05 PM", "2026-10-20T15:05:00+08:00"),
    ("limit reached, resets at 09:00", "2026-10-21T09:00:00+08:00"),                 # 已过 → 明天
    ("usage limit, try again at 2026-10-21 04:00", "2026-10-21T04:00:00+08:00"),
    ("You've hit your usage limit. try again at Oct 21st, 2026 5:04 AM.", "2026-10-21T05:04:00+08:00"),
    ("Claude AI usage limit reached|1792483200", "2026-10-20T16:00:00+08:00"),
])
def test_parse_reset(text, expect):
    assert TM.parse_reset(text, base=ts("2026-10-20T12:00:00+08:00")) == ts(expect)


def test_parse_reset_unknown_returns_none():
    assert TM.parse_reset("Error: 429 Too Many Requests", base=ts("2026-10-20T12:00:00+08:00")) is None


@pytest.mark.parametrize("line,hit", [
    ("Error: 429 Too Many Requests", True), ("HTTP 429 rate limited", True), ("Claude usage limit reached", True),
    ("try again in 5 minutes", True), ("You've hit your limit", True),
    ("implemented the rate limiter in api/limits.py", False), ("tests: 429 passed", False), ("all green", False),
])
def test_rate_limit_patterns(line, hit):
    assert bool(TM.rate_limit_line("ok\n" + line)) is hit


# ---------- 解析：时间窗 ----------
@pytest.mark.parametrize("spec,when,open_", [
    ("trading:cn", "2026-10-20T10:00:00+08:00", True),
    ("trading:cn", "2026-10-20T12:00:00+08:00", False),      # 午休
    ("trading:cn", "2026-10-20T13:30:00+08:00", True),
    ("trading:cn", "2026-10-20T15:00:00+08:00", False),      # 收盘（右端不含）
    ("trading:cn", "2026-10-24T10:00:00+08:00", False),      # 周六
    ("trading:cn", "2026-10-01T10:00:00+08:00", False),      # 节假日（配置）
    ("mon-fri 09:30-15:00", "2026-10-20T12:00:00+08:00", True),
    ("mon-fri 09:30-15:00", "2026-10-01T12:00:00+08:00", True),  # 显式写法不排节假日
    ("mon-fri 09:30-15:00 !holidays", "2026-10-01T12:00:00+08:00", False),
    ("daily 22:00-02:00", "2026-10-20T23:30:00+08:00", True),
    ("daily 22:00-02:00", "2026-10-21T01:30:00+08:00", True),
    ("daily 22:00-02:00", "2026-10-21T03:00:00+08:00", False),
    ("sat,sun 10:00-12:00; wed 08:00-09:00", "2026-10-21T08:30:00+08:00", True),
    ("night", "2026-10-20T23:00:00+08:00", True),            # 配置里的自定义预设
])
def test_window_open(spec, when, open_):
    cfg = {"tz": "Asia/Shanghai", "holidays": ["2026-10-01"], "presets": {"night": "daily 21:00-23:59"}}
    assert TM.window_open(spec, cfg, ts(when)) is open_


@pytest.mark.parametrize("bad", ["mon-fri", "someday 09:00-10:00", "mon-fri 9-10", "trading:moon"])
def test_window_bad_spec(bad):
    with pytest.raises(ValueError):
        TM.window_open(bad, {})


# ---------- 额度暂停（流水线）----------
def test_rate_limit_report_pauses_role_and_resumes_without_rework(loop):
    loop.project("AB")
    loop.plan(build=["ratelimit"])
    loop.add("AB")
    loop.tick("AB")                                          # 派工；工人打印额度提示并回报失败
    loop.tick("AB")                                          # 收回报 → 判定额度
    it = loop.item("AB")
    assert it["state"] == "queued" and it["round"] == 0 and it["rate_waits"] == 1 and it["model_i"] == 0
    rl = json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]
    assert rl["build"]["until"] == ts("2026-10-20T17:00:00+08:00")
    assert "verify" in rl                                    # 同一个账号（同一个命令）的岗位一起停
    sent = loop.telegram_sent()
    assert len(sent) == 1 and "额度用完" in sent[0]["text"] and "10-20 17:00" in sent[0]["text"]
    loop.tick("AB"); loop.tick("AB")
    s = loop.status_json("AB")
    assert s["items"][0]["state"] == "等额度" and s["items"][0]["waiting"] == "rate_limit"
    assert s["rate_limits"] and s["rate_limits"][0]["until"] == "2026-10-20T17:00:00+08:00"
    assert len([w for w in loop.workers() if w["role"] == "build"]) == 1
    assert len(loop.telegram_sent()) == 1                    # 只推一次
    loop.env["EVO_NOW"] = "2026-10-20T17:01:00+08:00"
    st = loop.run_until("AB", state_is("merged"))
    it = st["items"]["AB-FIX-001"]
    assert it["round"] == 0 and it["pushed"] == loop.remote_head("AB")
    assert not any("轮返工" in l for l in st["log"])
    assert "上一次因订阅额度用完中断" in [w for w in loop.workers() if w["role"] == "build"][-1]["spec"]
    assert any(e["kind"] == "rate_limit_resumed" for e in loop.outbox())


def test_rate_limit_seen_in_terminal_when_worker_hangs(loop):
    loop.write_global({"limits": {"rate_limit_idle_minutes": 0}})
    loop.env["FAKE_RL_TEXT"] = "You've hit your usage limit. Try again in 2 hours."
    loop.project("AB")
    loop.plan(build=["ratelimit-hang"])
    loop.add("AB")
    loop.tick("AB")                                          # 派工；工人打印提示后不回报；第一次看到只记下
    assert loop.item("AB")["state"] == "building"
    loop.tick("AB")                                          # 第二次同样的尾巴 → 判定额度
    it = loop.item("AB")
    assert it["state"] == "queued" and it["round"] == 0 and not it.get("stalled")
    rl = json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]["build"]
    assert rl["until"] == ts("2026-10-20T14:00:00+08:00") and not rl["guessed"]


def test_rate_limit_without_reset_time_defaults_to_60_minutes(loop):
    loop.env["FAKE_RL_TEXT"] = "Error: 429 Too Many Requests"
    loop.project("AB")
    loop.plan(verify=["ratelimit"])
    loop.add("AB")
    loop.run_until("AB", lambda s: s["items"]["AB-FIX-001"].get("rate_waits"))
    it = loop.item("AB")
    assert it["state"] == "built" and it["round"] == 0       # 验收岗停：施工成果留着，只重排验收
    rl = json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]["verify"]
    assert rl["until"] == ts("2026-10-20T13:00:00+08:00") and rl["guessed"]
    loop.env["EVO_NOW"] = "2026-10-20T13:00:30+08:00"
    loop.run_until("AB", state_is("merged"))
    assert len([w for w in loop.workers() if w["role"] == "build"]) == 1


# ---------- 施工报失败（以前会被当成交付送去验收，然后永远卡住）----------
def test_build_failure_is_rework_not_delivery(loop):
    loop.project("AB")
    loop.plan(build=["fail"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"))
    it = st["items"]["AB-FIX-001"]
    assert it["round"] == 1
    assert "施工报告失败" in [w for w in loop.workers() if w["role"] == "build"][1]["spec"]


# ---------- 用量 ----------
def test_usage_counters_and_abnormal_alert(loop):
    loop.write_global({"limits": {"usage_item_runs": 3}})
    loop.project("AB")
    loop.plan(verify=["fail"])
    loop.add("AB")
    st = loop.run_until("AB", state_is("merged"))
    assert st["usage"]["build"]["runs"] == 2 and st["usage"]["verify"]["runs"] == 2
    it = st["items"]["AB-FIX-001"]
    assert it["usage"]["runs"] == 4 and it["usage"]["minutes"] >= 0
    ab = [m for m in loop.telegram_sent() if "用量异常" in m["text"]]
    assert len(ab) == 1 and "已派工 4 次" in ab[0]["text"]
    s = loop.status_json("AB")
    assert s["usage"]["roles"]["build"]["runs"] == 2 and s["items"][0]["usage"]["runs"] == 4
    assert s["usage"]["tokens"] is None
    assert "派工 4 次" in loop.ok("-p", "AB", "status").stdout


def test_magpie_usage_log_tokens(loop):
    log = os.path.join(loop.tmp, "magpie-usage.jsonl")
    with open(log, "w") as f:
        f.write(json.dumps({"model": "glm/glm-5.3-flash", "total_tokens": 1200, "project": "AB"}) + "\n")
        f.write(json.dumps({"model": "glm/glm-5.3-flash", "input_tokens": 100, "output_tokens": 50}) + "\n")
        f.write(json.dumps({"model": "deepseek/deepseek-v4.1", "tokens": 7}) + "\n")
    loop.write_global({"magpie": {"usage_url": log}})
    loop.project("AB")
    t = loop.status_json("AB")["usage"]["tokens"]
    assert t["by_model"] == {"glm/glm-5.3-flash": 1350, "deepseek/deepseek-v4.1": 7} and t["project"] == 1200


# ---------- 时间窗（流水线）----------
def test_window_gating_waits_then_starts(loop):
    loop.project("AB")
    r = loop.evo("-p", "AB", "add", "--kind", "ops", "--title", "调整行情同步任务", "--scope", "jobs/", "--window", "mon-fri 9-10")
    assert r.returncode != 0 and "看不懂的时间窗" in (r.stderr + r.stdout)
    loop.ok("-p", "AB", "add", "--kind", "ops", "--title", "调整行情同步任务", "--scope", "jobs/", "--window", "trading:cn")
    loop.tick("AB"); loop.tick("AB")                         # 12:00 午休，窗外
    it = loop.item("AB")
    assert it["state"] == "queued" and it["window"] == "trading:cn"
    assert loop.status_json("AB")["items"][0]["state"] == "等窗口"
    assert "等窗口" in loop.ok("-p", "AB", "status").stdout
    assert loop.workers() == []
    assert len([l for l in loop.state("AB")["log"] if "等窗口" in l]) == 1     # 只记一次
    loop.env["EVO_NOW"] = "2026-10-20T13:05:00+08:00"
    loop.tick("AB")
    assert loop.item("AB")["state"] != "queued"
    assert "时间窗: trading:cn" in loop.workers()[0]["spec"]


# ---------- 决策岗批量叫醒 ----------
def decider_global(loop, **lim):
    py = sys.executable
    loop.write_global({"roles": {"decide": {"cmd": f"{py} {os.path.join(KIT, 'tests', 'fakes', 'worker.py')} decide",
                                            "models": ["model-x"], "prompt": "roles/decider.md", "boot_seconds": 0}},
                       "limits": {"rework_rounds": 0, **lim}})


def test_decider_woken_batched_at_most_every_30_minutes(loop):
    decider_global(loop)
    loop.project("AB")
    loop.plan(verify=["fail", "fail", "fail"])
    loop.add("AB", "修复注册页验证码不刷新", "web/")
    loop.add("AB", "修复设置页保存失败", "api/")
    loop.run_until("AB", lambda s: all(i["state"] == "escalated" for i in s["items"].values()))
    dec = [w for w in loop.workers() if w["role"] == "decide"]
    assert len(dec) == 1                                     # 两件一批
    assert "AB-FIX-001" in dec[0]["spec"] and "AB-FIX-002" in dec[0]["spec"] and "决策岗" in dec[0]["spec"]
    loop.add("AB", "修复首页加载很慢", "home/")
    loop.run_until("AB", lambda s: s["items"]["AB-FIX-003"]["state"] == "escalated")
    loop.tick("AB")
    assert len([w for w in loop.workers() if w["role"] == "decide"]) == 1      # 30 分钟内不再叫
    loop.env["EVO_NOW"] = "2026-10-20T12:31:00+08:00"
    loop.tick("AB")
    dec = [w for w in loop.workers() if w["role"] == "decide"]
    assert len(dec) == 2 and "【新】AB-FIX-003" in dec[1]["spec"] and "【上批已交，仍在等】AB-FIX-001" in dec[1]["spec"]
    loop.env["EVO_NOW"] = "2026-10-20T13:10:00+08:00"
    loop.tick("AB")
    assert len([w for w in loop.workers() if w["role"] == "decide"]) == 2      # 没有新的：不重复叫
    s = loop.status_json("AB")
    assert s["decider"]["last_woken"] == "2026-10-20T12:31:00+08:00" and s["usage"]["roles"]["decide"]["runs"] == 2


def test_no_decide_role_configured_means_no_wake(loop):
    loop.write_global({"limits": {"rework_rounds": 0}})
    loop.project("AB")
    loop.plan(verify=["fail"])
    loop.add("AB")
    loop.run_until("AB", state_is("escalated"))
    loop.tick("AB")
    assert [w for w in loop.workers() if w["role"] == "decide"] == []


# ---------- 10-23 #32 #33：上游故障（终端挂住）短暂停重排、只停出事的岗、重排不计入用量异常 ----------
UP = 'API Error: 504 Post "https://api.artbloom.tech/v1/messages?beta=true": proxyconn'


def test_upstream_seen_in_terminal_when_worker_hangs(loop):
    loop.write_global({"limits": {"rate_limit_idle_minutes": 0, "usage_item_runs": 1}})
    loop.env["FAKE_RL_TEXT"] = UP
    loop.project("AB")
    loop.plan(build=["ratelimit-hang"])
    loop.add("AB")
    loop.tick("AB")                                          # 派工；终端停在 504 上不回报；第一次只记下
    assert loop.item("AB")["state"] == "building"
    loop.tick("AB")                                          # 第二次同样的尾巴 → 上游故障，短暂停后原样重排
    it = loop.item("AB")
    assert it["state"] == "queued" and it["round"] == 0 and not it.get("stalled") and it["rate_waits"] == 1
    roles = json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]
    assert roles["build"]["kind"] == "upstream" and not roles["build"]["guessed"]
    assert "verify" not in roles                              # 同账号（同一个命令）的验收岗不连坐
    assert any(e["kind"] == "upstream_down" for e in loop.outbox())
    assert not any("疑似卡住" in l for l in loop.state("AB")["log"])
    # 到点后再派工：派工 2 次，其中 1 次是上游重排 → 实际 1 次，不超过上限 1，不报用量异常
    loop.env["EVO_NOW"] = "2026-10-20" + "T15:00:00+08:00"
    loop.env.pop("FAKE_RL_TEXT")
    loop.plan(build=["ok"])
    loop.tick("AB")
    it = loop.item("AB")
    assert it["usage"]["runs"] == 2 and it["rate_waits"] == 1
    assert not [m for m in loop.telegram_sent() if "用量异常" in m["text"]]


def test_plain_output_in_hung_terminal_not_upstream(loop):
    loop.write_global({"limits": {"rate_limit_idle_minutes": 0}})
    loop.env["FAKE_RL_TEXT"] = "Running tests... 12 passed"
    loop.project("AB")
    loop.plan(build=["ratelimit-hang"])
    loop.add("AB")
    loop.tick("AB"); loop.tick("AB")
    it = loop.item("AB")
    assert it["state"] == "building" and not it.get("rate_waits")
    assert not os.path.exists(os.path.join(loop.root, "ratelimit.json")) or \
        not json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]


def test_quota_still_pauses_whole_account(loop):
    loop.write_global({"limits": {"rate_limit_idle_minutes": 0}})
    loop.env["FAKE_RL_TEXT"] = "API Error: 503 no auth available (last error: 429 rate limit, try again in 2 hours)"
    loop.project("AB")
    loop.plan(build=["ratelimit-hang"])
    loop.add("AB")
    loop.tick("AB"); loop.tick("AB")
    roles = json.load(open(os.path.join(loop.root, "ratelimit.json")))["roles"]
    assert roles["build"]["kind"] == "quota" and "verify" in roles   # 额度按账号一起停
