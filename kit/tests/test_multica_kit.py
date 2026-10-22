"""kit/multica：补丁脚本可重复、找不到原句会失败；脚本语法；不含真实用户路径。"""
import shutil, subprocess, pathlib, pytest

KIT = pathlib.Path(__file__).resolve().parents[1] / "multica"
NODE = shutil.which("node")

SAMPLE = '''async function watchUserPatches(ctx) {
  const hmr = ctx.get("hmr");
  if (hmr === void 0) throw new Error("dsh: user patch-layer watching requires the Cordis HMR service");
  hmr.registerConfig();
}
'''

@pytest.mark.skipif(not NODE, reason="no node")
def test_patch_idempotent(tmp_path):
    f = tmp_path / "index.js"; f.write_text(SAMPLE)
    r = subprocess.run([NODE, str(KIT / "patch-dsh-boot.mjs"), str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = f.read_text()
    assert "evo-multica:hmr-poll" in out and "let hmr = ctx.get" in out and "const hmr" not in out
    subprocess.run([NODE, "--check", str(f)], check=True)
    r2 = subprocess.run([NODE, str(KIT / "patch-dsh-boot.mjs"), str(f)], capture_output=True, text=True)
    assert r2.returncode == 0 and f.read_text() == out

@pytest.mark.skipif(not NODE, reason="no node")
def test_patch_fails_loud_when_pattern_missing(tmp_path):
    f = tmp_path / "index.js"; f.write_text("export const x = 1;\n")
    r = subprocess.run([NODE, str(KIT / "patch-dsh-boot.mjs"), str(f)], capture_output=True, text=True)
    assert r.returncode == 1

def test_scripts_syntax_and_no_real_paths():
    for sh in ["install.sh", "open-multica.sh"]:
        subprocess.run(["bash", "-n", str(KIT / sh)], check=True)
    for p in KIT.iterdir():
        t = p.read_text()
        assert "/Users/" not in t and "zhuyuechen" not in t and "100.90." not in t, p

def _run(args, env_extra, home):
    import os
    env = dict(os.environ, HOME=str(home), **env_extra)
    return subprocess.run(["bash", str(KIT / "install.sh"), *args], capture_output=True, text=True, env=env)

def test_uninstall_needs_yes_and_only_deletes_multica_dir(tmp_path):
    root = tmp_path / "x" / "multica"; (root / "bin").mkdir(parents=True)
    r = _run(["--uninstall"], {"EVO_MULTICA_DIR": str(root)}, tmp_path)
    assert r.returncode == 1 and root.exists() and "--yes" in r.stdout
    bad = tmp_path / "important"; bad.mkdir()
    r = _run(["--uninstall", "--yes"], {"EVO_MULTICA_DIR": str(bad)}, tmp_path)
    assert r.returncode == 1 and bad.exists()
    r = _run(["--uninstall", "--yes"], {"EVO_MULTICA_DIR": str(root)}, tmp_path)
    assert r.returncode == 0 and not root.exists()

def test_throttle_must_be_integer(tmp_path):
    r = _run([], {"MULTICA_THROTTLE": "abc", "EVO_MULTICA_DIR": str(tmp_path / "multica")}, tmp_path)
    assert r.returncode == 2

def test_install_has_round2_fixes():
    t = (KIT / "install.sh").read_text()
    for needle in ["pnpm-lock.yaml", "--no-package-lock", "trap on_fail EXIT", "probe.log\"   # 成功也留底",
                   "--check \"$BOOTJS\"", "<integer>$THROTTLE</integer>", "MAGPIE_KEY_FROM_KEYCHAIN", "--update-src", "pull --ff-only"]:
        assert needle in t, needle
