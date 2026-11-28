import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import engine_gaps as G

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _w(root, rel, text, nl="\n"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", nl))


def _cap(id, kanit=(), test=(), acik=(), skill="sk", onay=False):
    d = {"id": id, "motor": "m", "isci": "w", "skill": skill, "yetenek": id, "kanit": list(kanit), "test": list(test)}
    if acik: d["acik_gorev"] = list(acik)
    if onay: d["insan_onayi"] = True
    return d


def _proj(tmp_path):
    root = str(tmp_path)
    _w(root, "tools/alpha.py", "def run():\n    return 1\n\ndef _gizli():\n    squash = 2\n")
    _w(root, "tests/test_alpha.py", "import alpha\n")
    _w(root, "tests/test_other.py", "import beta\n")
    return root


def _status(root, caps):
    rep = G.check(root, {"yetenekler": caps})
    return {r["id"]: r["durum"] for r in rep["yetenekler"]}, rep


def test_durum_kanittan_hesaplanir(tmp_path):
    root = _proj(tmp_path)
    st, rep = _status(root, [
        _cap("V", [{"modul": "tools/alpha.py", "sembol": "run"}], ["tests/test_alpha.py"]),
        _cap("D", [{"modul": "tools/alpha.py", "desen": "squash"}], ["tests/test_alpha.py"]),
        _cap("P", [{"modul": "tools/alpha.py", "sembol": "_gizli"}], ["tests/test_alpha.py"], acik=["X1"]),
        _cap("Y"),
        _cap("T0", [{"modul": "tools/alpha.py", "sembol": "run"}]),
        _cap("T1", [{"modul": "tools/alpha.py", "sembol": "run"}], ["tests/test_other.py"]),
        _cap("T2", [{"modul": "tools/alpha.py", "sembol": "run"}], ["tests/test_yok.py"]),
        _cap("B1", [{"modul": "tools/alpha.py", "sembol": "uydurma"}], ["tests/test_alpha.py"]),
        _cap("B2", [{"modul": "tools/yok.py", "sembol": "run"}], ["tests/test_alpha.py"]),
        _cap("B3", [{"modul": "tools/alpha.py", "desen": "parallax"}], ["tests/test_alpha.py"]),
    ])
    assert st == {"V": "VAR", "D": "VAR", "P": "KISMI", "Y": "YOK", "T0": "TESTSIZ", "T1": "TESTSIZ",
                  "T2": "TESTSIZ", "B1": "KANIT_BOZUK", "B2": "KANIT_BOZUK", "B3": "KANIT_BOZUK"}
    # öncelik: harita yalanları önce, sonra yokluk, sonra testsizlik, sonra kısmi
    assert rep["eksikler"][:3] == ["B1", "B2", "B3"]
    assert rep["eksikler"].index("Y") < rep["eksikler"].index("T0") < rep["eksikler"].index("P")
    assert "V" not in rep["eksikler"]


def test_bilerek_bozma_sembol_silinince_kanit_bozuk(tmp_path):
    root = _proj(tmp_path)
    caps = [_cap("V", [{"modul": "tools/alpha.py", "sembol": "run"}], ["tests/test_alpha.py"])]
    assert _status(root, caps)[0]["V"] == "VAR"
    _w(root, "tools/alpha.py", "def baska():\n    return 1\n")
    assert _status(root, caps)[0]["V"] == "KANIT_BOZUK"
    _w(root, "tools/alpha.py", "def run(:\n")  # sözdizimi bozuk modül VAR sayılmaz
    assert _status(root, caps)[0]["V"] == "KANIT_BOZUK"


def test_insan_onayi_teknik_var_ile_ayri_raporlanir(tmp_path):
    root = _proj(tmp_path)
    st, rep = _status(root, [_cap("V", [{"modul": "tools/alpha.py", "sembol": "run"}], ["tests/test_alpha.py"], onay=True)])
    assert st["V"] == "VAR" and rep["insan_onayi_bekleyen"] == ["V"]
    assert "İnsan onayı" in G.render_md(rep)


def test_skill_blogu_yazilir_tekrar_yazmaz_crlf_korur_dosya_olusturmaz(tmp_path):
    root = _proj(tmp_path)
    _w(root, "skills/sk/SKILL.md", "---\nname: sk\n---\n# sk\nmetin\n", nl="\r\n")
    caps = [_cap("V", [{"modul": "tools/alpha.py", "sembol": "run"}], ["tests/test_alpha.py"]),
            _cap("Y", skill="olmayan")]
    rep = G.check(root, {"yetenekler": caps})
    sk = {s["skill"]: s for s in rep["skilller"]}
    assert any("anmıyor" in p for p in sk["sk"]["sorunlar"])
    assert sk["olmayan"]["var"] is False
    assert G.write_skills(rep, root) == [os.path.join("skills", "sk", "SKILL.md")]
    assert not os.path.exists(os.path.join(root, "skills", "olmayan"))
    raw = open(os.path.join(root, "skills/sk/SKILL.md"), "rb").read().decode("utf-8")
    assert "metin" in raw and "tools/alpha.py" in raw and "\n" not in raw.replace("\r\n", "")
    rep2 = G.check(root, {"yetenekler": caps})
    assert {s["skill"]: s for s in rep2["skilller"]}["sk"]["sorunlar"] == []
    assert G.write_skills(rep2, root) == []  # aynı içerik: dosyaya dokunmaz
    # yetenek durumu değişince blok yerinde güncellenir, ikinci blok eklenmez
    caps[0]["acik_gorev"] = ["Z9"]
    G.write_skills(G.check(root, {"yetenekler": caps}), root)
    raw = open(os.path.join(root, "skills/sk/SKILL.md"), encoding="utf-8").read()
    assert raw.count(G.BLOCK_START) == 1 and "KISMI" in raw and "Z9" in raw


def test_gercek_harita_dogru_ve_kimlikler_tekil():
    reg = G.load(REPO)
    ids = [c["id"] for c in reg["yetenekler"]]
    assert len(ids) == len(set(ids)) and len(ids) >= 60
    rep = G.check(REPO)
    bad = [r["id"] + ": " + "; ".join(r["neden"]) for r in rep["yetenekler"] if r["durum"] == "KANIT_BOZUK"]
    assert bad == []  # harita koddan farklı bir şey iddia etmiyor
    for c in reg["yetenekler"]:
        for e in c.get("kanit", []):
            assert ("sembol" in e) != ("desen" in e), c["id"]
    assert rep["toplam"]["YOK"] > 0  # eksikler gizlenmiyor


def test_cli_json_ve_md(tmp_path):
    j, m = str(tmp_path / "r.json"), str(tmp_path / "r.md")
    assert G.main(["--json", j, "--md", m]) == 0
    rep = json.load(open(j, encoding="utf-8"))
    assert rep["yetenek_sayisi"] == len(rep["yetenekler"])
    assert "## Eksikler" in open(m, encoding="utf-8").read()
