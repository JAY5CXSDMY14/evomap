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
