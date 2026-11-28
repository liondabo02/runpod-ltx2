import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import software_dept as S
import office_live

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(root, *a):
    subprocess.run(["git", *a], cwd=root, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})


def _w(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


TEST = ("import os, sys\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))\n"
        "import calc\n"
        "def test_topla():\n    assert calc.topla(2, 3) == 5\n")


def _repo(tmp_path):
    """Eski commit: hatalı topla. Yeni commit: düzeltme + yeni test."""
    root = str(tmp_path / "r")
    os.makedirs(root)
    _git(root, "init", "-q")
    _w(root, "tools/calc.py", "def topla(a, b):\n    return a - b\n")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "H1 ilk hali")
    _w(root, "tools/calc.py", "def topla(a, b):\n    return a + b\n")
    _w(root, "tests/test_calc.py", TEST)
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "H2 topla duzeltildi")
    return root


def _worktrees(root):
    out = subprocess.run(["git", "worktree", "list"], cwd=root, capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if l.strip()]


def test_kabul_yeni_kodda_gecer_eski_kodda_duser(tmp_path):
    root = _repo(tmp_path)
    r = S.acceptance(root, ["tests/test_calc.py"])
    assert r["sonuc"] == "KABUL", r
    assert r["yeni_kod"]["exit"] == 0 and r["eski_kod"]["exit"] not in (0, 124, 127)
    assert len(_worktrees(root)) == 1  # geçici çalışma kopyası temizlendi
    rec = open(os.path.join(root, S.STATE_DIR, "kabul.jsonl"), encoding="utf-8").read().splitlines()
    assert json.loads(rec[-1])["sonuc"] == "KABUL"


def test_bilerek_bozma_eski_kodda_da_gecen_test_reddedilir(tmp_path):
    root = _repo(tmp_path)
    _w(root, "tests/test_bos.py", "def test_hep_gecer():\n    assert True\n")
    r = S.acceptance(root, ["tests/test_bos.py"])
    assert r["sonuc"] == "RED" and "ESKI_KODDA_DA_GECIYOR" in r["neden"]


def test_yeni_kodda_dusen_test_reddedilir(tmp_path):
    root = _repo(tmp_path)
    _w(root, "tools/calc.py", "def topla(a, b):\n    return 0\n")
    r = S.acceptance(root, ["tests/test_calc.py"])
    assert r["sonuc"] == "RED" and r["neden"] == "YENI_KODDA_DUSUYOR"
    assert "eski_kod" not in r


def test_kirmizi_adim_ancak_gerekceyle_atlanir(tmp_path):
    root = _repo(tmp_path)
    r = S.acceptance(root, ["tests/test_calc.py"], no_red_reason="yalnız yeniden adlandırma")
    assert r["sonuc"] == "KABUL_KIRMIZISIZ" and "yeniden adlandırma" in r["neden"]


def test_eski_surum_yoksa_kabul_yok(tmp_path):
    root = _repo(tmp_path)
    r = S.acceptance(root, ["tests/test_calc.py"], base="olmayan-dal")
    assert r["sonuc"] == "RED" and r["neden"] == "ESKI_KOD_HAZIRLANAMADI"


def test_ofis_senkron_gercek_commitleri_bir_kez_yazar_ve_ofiste_gorunur(tmp_path):
    root = _repo(tmp_path)
    ev = str(tmp_path / "events.jsonl")
    assert S.office_sync(root, events_path=ev) == 2
    assert S.office_sync(root, events_path=ev) == 0  # aynı commit iki kez yazılmaz
    rows = [json.loads(l) for l in open(ev, encoding="utf-8")]
    assert [r["worker"] for r in rows] == ["software", "software"]
    assert all(r["kind"] == "done" and r["job"].startswith("git-") for r in rows)
    assert rows[-1]["text"].startswith("motor geliştirmesi tamam") and "H2: topla duzeltildi" in rows[-1]["text"]
    assert rows[0]["at"] <= rows[1]["at"]
    _w(root, "x.txt", "1"); _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "serbest mesaj")
    assert S.office_sync(root, events_path=ev) == 1
    live = office_live.derive([("software", "Yazılım Şirketi", "motor geliştirme", True)],
                              [json.loads(l) for l in open(ev, encoding="utf-8")], [], False, 0)
    s = live[0]
    assert s["live"] is True and s["state"] == "idle" and s["last"]["ok"] is True
    assert "serbest mesaj" in s["last"]["text"]


def test_ofis_ve_harita_yazilim_departmanini_taniyor():
    import office_server
    assert "software" in office_live.INSTRUMENTED
    assert any(w[0] == "software" for w in office_server.WORKERS)
    import engine_gaps
    rep = engine_gaps.check(REPO)
    soft = [r for r in rep["yetenekler"] if r["isci"] == "software"]
    assert soft and all(r["durum"] == "VAR" for r in soft)
