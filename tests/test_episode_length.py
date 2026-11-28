"""V2: dizinin istediği en az süreden kısa plan TAM BÖLÜM olarak render edilmez; kısmi pencere etkilenmez."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import episode_length as el

BIBLE = {"episode_defaults": {"min_seconds": 480}}


def sheet(*spans):
    return {"beats": [{"t_start": a, "t_end": b} for a, b in spans]}


def test_kisa_plan_tam_bolum_olarak_durur():
    r = el.check(sheet((0, 38)), BIBLE, 0, 38, env={})
    assert r["problems"] and "480" in r["problems"][0]


def test_kismi_pencere_etkilenmez():
    assert el.check(sheet((0, 38)), BIBLE, 0, 12, env={})["problems"] == []


def test_yeterli_plan_gecer():
    spans = [(i * 40, i * 40 + 40) for i in range(12)]
    assert el.check(sheet(*spans), BIBLE, 0, 480, env={})["problems"] == []


def test_bosluklu_plan_480e_uzatilmis_sayilmaz():
    """Plan sonu 480 ama yalnız 60 sn vuruş var: boşluk süre sayılmaz."""
    r = el.check(sheet((0, 30), (450, 480)), BIBLE, 0, 480, env={})
    assert r["problems"] and r["covered_seconds"] == 60.0


def test_ust_uste_binen_vuruslar_iki_kez_sayilmaz():
    assert el.check(sheet((0, 300), (100, 300), (0, 300)), BIBLE, 0, 300, env={})["covered_seconds"] == 300.0


def test_bible_min_seconds_yoksa_kapi_yok():
    r = el.check(sheet((0, 38)), {}, 0, 38, env={})
    assert r["gated"] is False and r["problems"] == []


def test_bilerek_kisa_teslim_izni_raporlanir():
    r = el.check(sheet((0, 38)), BIBLE, 0, 38, env={"AHOS_ALLOW_SHORT": "1"})
    assert r["problems"] == [] and r["allowed_short"] is True


def test_bozuk_min_seconds_sessizce_gecmez():
    r = el.check(sheet((0, 38)), {"episode_defaults": {"min_seconds": "yok"}}, 0, 38, env={})
    assert r["problems"]


def test_render_worker_kisa_planda_planlayiciya_varmadan_durur(tmp_path, monkeypatch):
    import json, render_worker as rw
    monkeypatch.delenv("AHOS_ALLOW_SHORT", raising=False)
    ep = tmp_path / "ep"; ep.mkdir()
    json.dump(sheet((0, 38)), open(ep / "beat_sheet.json", "w"))
    def runner(*a, **k): raise AssertionError("render başladı")
    r = rw.run(str(ep), BIBLE, 0.0, 38.0, str(tmp_path), runner=runner)
    assert r["status"] == "BLOCKED" and r["error"] == "BOLUM_COK_KISA"
