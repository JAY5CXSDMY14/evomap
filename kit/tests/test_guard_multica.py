"""看门狗顺带给 Multica 执行端自愈（10-23）：被卸出 launchd → 重挂；加载了没在跑 → 拉起；推送一小时一次。"""
import json, os, subprocess

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(KIT, "selfmaint", "evo-guard.sh")

FAKE = r'''#!/bin/bash
echo "$*" >> "$CALLS"
case "$1" in
  print) [ -f "$LOADED" ] || exit 113; cat "$LOADED"; exit 0 ;;
  bootstrap) echo "state = running" > "$LOADED"; exit 0 ;;
  kickstart) echo "state = running" > "$LOADED"; exit 0 ;;
esac
exit 0
'''


def run(tmp_path, now):
    b = tmp_path / "bin"; b.mkdir(exist_ok=True)
    (b / "launchctl").write_text(FAKE); os.chmod(b / "launchctl", 0o755)
    (b / "sleep").write_text("#!/bin/bash\nexit 0\n"); os.chmod(b / "sleep", 0o755)
    plist = tmp_path / "m.plist"; plist.write_text("<plist/>")
    env = {**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "EVO_DIR": str(tmp_path / "evo"), "GUARD_NO_NET": "1",
           "GUARD_MULTICA_PLIST": str(plist), "CALLS": str(tmp_path / "calls"), "LOADED": str(tmp_path / "loaded"),
           "GUARD_NOW": str(now)}
    return subprocess.run(["bash", GUARD], env=env, capture_output=True, text=True)


def outbox(tmp_path):
    p = tmp_path / "evo" / "outbox.jsonl"
    return [json.loads(x) for x in open(p)] if p.exists() else []


def test_rebootstraps_when_unloaded_and_rate_limits_push(tmp_path):
    r = run(tmp_path, 1000)
    assert r.returncode == 0, r.stderr
    calls = (tmp_path / "calls").read_text()
    assert "bootstrap" in calls and "enable" in calls
    ob = outbox(tmp_path)
    assert len(ob) == 1 and ob[0]["kind"] == "multica_daemon_heal" and "重新挂上" in ob[0]["body"]
    assert "重新挂上" in (tmp_path / "evo" / "logs" / "guard.log").read_text()
    # 正常在跑：不动、不推
    run(tmp_path, 1060)
    assert len(outbox(tmp_path)) == 1
    # 又被卸掉，但不到一小时：只记日志、不再推
    os.remove(tmp_path / "loaded")
    run(tmp_path, 1200)
    assert len(outbox(tmp_path)) == 1
    assert (tmp_path / "evo" / "logs" / "guard.log").read_text().count("重新挂上") == 2


def test_kickstarts_when_loaded_but_not_running(tmp_path):
    (tmp_path / "loaded").write_text("state = not running\n")
    run(tmp_path, 1000)
    assert "kickstart" in (tmp_path / "calls").read_text()
    assert "已拉起" in outbox(tmp_path)[0]["body"]


def test_no_plist_does_nothing(tmp_path):
    os.makedirs(tmp_path / "x")
    env = {**os.environ, "EVO_DIR": str(tmp_path / "evo"), "GUARD_NO_NET": "1",
           "GUARD_MULTICA_PLIST": str(tmp_path / "x" / "missing.plist")}
    r = subprocess.run(["bash", GUARD], env=env, capture_output=True, text=True)
    assert r.returncode == 0 and not outbox(tmp_path)
