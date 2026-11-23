import os, sys, subprocess, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import style_profile as sp
T = os.path.join(os.path.dirname(__file__), "..", "tools")


def run(args):
    return subprocess.run([sys.executable, os.path.join(T, "adapt_source.py")] + args, capture_output=True, text=True)


def test_presets(monkeypatch):
    monkeypatch.setenv("AHOS_STYLE", "masal")
    assert sp.current()["dust"] is False
    monkeypatch.setenv("AHOS_STYLE", "slapstick")
    assert sp.current()["energy"] > 1.4


def test_adapt_requires_rights(tmp_path):
    f = tmp_path / "s.txt"; f.write_text("Ali eve gitti. Ayşe güldü! Neden?", encoding="utf-8")
    assert run(["--source-file", str(f), "--out", str(tmp_path / "o"), "--mode", "adapt"]).returncode == 2
    assert run(["--source-file", str(f), "--out", str(tmp_path / "o"), "--mode", "adapt", "--rights", "own", "--proof", "kendi metnim"]).returncode == 0
    f2 = tmp_path / "t.txt"; f2.write_text("Scooby ve Shaggy kaçar.", encoding="utf-8")
    assert run(["--source-file", str(f2), "--out", str(tmp_path / "o2"), "--mode", "adapt", "--rights", "own", "--proof", "x"]).returncode == 2


def test_inspire_has_no_names(tmp_path):
    f = tmp_path / "s.txt"; f.write_text("Veysel parka gitti. Veysel güldü. Salih koştu!", encoding="utf-8")
    r = run(["--source-file", str(f), "--out", str(tmp_path / "o")]); assert r.returncode == 0
    j = open(tmp_path / "o" / "adaptation_plan.json", encoding="utf-8").read()
    assert "Veysel" not in j and "Salih" not in j and "özgünleştirme" in j
