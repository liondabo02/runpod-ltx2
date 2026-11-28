"""K1h: eylem metni/storyboard bir eylem istiyorsa üretim verisinde karşılığı olmadan render başlamaz. İki farklı sentetik proje."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import action_trace as at  # noqa: E402
import render_worker as rw  # noqa: E402

# İki proje: farklı dil, farklı ipucu sözleri, farklı oyuncu/nesne adları. Motor ikisinin de sözcüklerini bilmez.
PROJECTS = {
    "deniz_tr": {"a": "kaptan", "b": "miço", "prop": "lantern",
                 "text": {"point": "Kaptan uzaktaki feneri gösterir.", "give": "Kaptan feneri miçoya uzatır."},
                 "cues": {"point": ["göster", "işaret ed"], "give": ["uzatır"]}},
    "garden_en": {"a": "robin", "b": "sam", "prop": "shovel",
                  "text": {"point": "Robin points at the shovel.", "give": "Robin hands over the shovel to Sam."},
                  "cues": {"point": ["points at"], "give": ["hands over"]}},
}


def beat(p, kind, with_data=True, **extra):
    a, b, prop = p["a"], p["b"], p["prop"]
    ch = {"motion": {a: {"kind": "idle", "x0": 0.5}, b: {"kind": "idle", "x0": -0.5}}}
    if with_data and kind == "point":
        ch["points"] = [{"by": a, "to": {"prop": prop}, "t": 1.0}]
        ch["objects"] = [{"prop": prop, "track": [{"t": 0, "at": [-1.5, 0.0]}, {"t": 8, "at": [-1.5, 0.0]}]}]
    if with_data and kind == "give":
        ch["objects"] = [{"prop": prop, "track": [{"t": 0, "holder": a}, {"t": 2.0, "holder": a}, {"t": 3.4, "holder": b}]}]
    return dict({"t_start": 0, "t_end": 8, "shot_id": "s1", "characters": [a, b], "action": p["text"][kind], "choreo": ch}, **extra)


def series(tmp_path, name, cues=True):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    if cues:
        (d / "action_cues.json").write_text(json.dumps(PROJECTS[name]["cues"] if cues is True else cues, ensure_ascii=False), encoding="utf-8")
    return str(d)


def rules(rep):
    return [p["rule"] for p in rep["problems"]]


@pytest.mark.parametrize("name", sorted(PROJECTS))
@pytest.mark.parametrize("kind", ["point", "give"])
def test_action_text_passes_with_data_and_is_caught_when_the_data_is_removed(tmp_path, name, kind):
    sd, p = series(tmp_path, name), PROJECTS[name]
    good = at.check({"beats": [beat(p, kind)]}, sd)
    assert good["problems"] == [] and good["untraced_beats"] == []
    bad = at.check({"beats": [beat(p, kind, with_data=False)]}, sd)                      # bilerek bozma: veri silindi
    assert rules(bad) == ["METIN_EYLEMI_IZSIZ"] and kind in bad["problems"][0]["why"]


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_waiver_needs_a_reason(tmp_path, name):
    sd, p = series(tmp_path, name), PROJECTS[name]
    ok = at.check({"beats": [beat(p, "point", with_data=False, action_waivers={"point": "jest bilerek yok"})]}, sd)
    assert ok["problems"] == [] and ok["beats"][0]["waived"] == {"point": "jest bilerek yok"}
    empty = at.check({"beats": [beat(p, "point", with_data=False, action_waivers={"point": "  "})]}, sd)
    assert rules(empty) == ["EYLEM_ALANI_GECERSIZ", "METIN_EYLEMI_IZSIZ"]


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_required_actions_check_who_and_what_without_any_word_list(tmp_path, name):
    sd, p = series(tmp_path, name, cues=False), PROJECTS[name]
    a, b, prop = p["a"], p["b"], p["prop"]
    for kind, to in (("point", {"prop": prop}), ("give", b)):
        want = [{"do": kind, "by": a, "to": to}]
        assert at.check({"beats": [beat(p, kind, required_actions=want)]}, sd)["problems"] == []
        for broken in (beat(p, kind, with_data=False, required_actions=want),                      # veri yok
                       beat(p, kind, required_actions=[{"do": kind, "by": b, "to": to}]),         # yanlış kişi
                       beat(p, kind, required_actions=[{"do": kind, "by": a, "to": "baska"}])):   # yanlış hedef
            assert rules(at.check({"beats": [broken]}, sd)) == ["EYLEM_UYGULANMAMIS"]
    junk = beat(p, "point", required_actions=[{"do": "uc", "by": a}, {"do": "point", "by": "yok_biri"}])
    assert rules(at.check({"beats": [junk]}, sd)) == ["EYLEM_ALANI_GECERSIZ"] * 2


def test_unchecked_text_is_reported_not_silently_passed(tmp_path):
    p = PROJECTS["deniz_tr"]
    rep = at.check({"beats": [beat(p, "point", with_data=False)]}, series(tmp_path, "deniz_tr", cues=False))
    assert rep["problems"] == [] and rep["untraced_beats"] == ["s1"] and rep["cue_file"] is False


@pytest.mark.parametrize("cues", [{"piont": ["göster"]}, {"point": []}, {"point": "göster"}, {"point": ["g"]}, {}, ["point"]])
def test_broken_cue_file_blocks_instead_of_disabling_the_check(tmp_path, cues):
    d = tmp_path / "x"
    d.mkdir()
    (d / "action_cues.json").write_text(json.dumps(cues), encoding="utf-8")
    assert set(rules(at.check({"beats": []}, str(d)))) == {"IPUCU_SOZLUGU_GECERSIZ"}
    (d / "action_cues.json").write_text("{bozuk", encoding="utf-8")
    assert rules(at.check({"beats": []}, str(d))) == ["IPUCU_SOZLUGU_GECERSIZ"]


def test_cue_matches_only_at_word_start_and_window_limits_the_check(tmp_path):
    assert at.cue_hits("Kaptan gösterir.", {"point": ["göster"]}) == {"point": "göster"}
    assert at.cue_hits("İŞARET EDER", {"point": ["işaret ed"]}) == {"point": "işaret ed"}
    assert at.cue_hits("Repoints at it", {"point": ["points at"]}) == {}
    p = PROJECTS["deniz_tr"]
    sheet = {"beats": [beat(p, "point"), dict(beat(p, "point", with_data=False), t_start=8, t_end=16, shot_id="s2")]}
    sd = series(tmp_path, "deniz_tr")
    assert at.check(sheet, sd, 0, 8)["problems"] == []
    assert [x["beat"] for x in at.check(sheet, sd, 8, 16)["problems"]] == ["s2"]


def test_render_gate_stops_before_planning_when_the_gesture_data_is_removed_from_the_real_sheet(tmp_path, monkeypatch):
    """Depodaki dizi verisi: e900'ün kopyasından gösterme verisi silinirse render planlayıcıya bile varmaz."""
    sdir = os.path.join(ROOT, "series", "ahos-bizim-aile")
    sheet = json.load(open(os.path.join(sdir, "episodes", "e900_kabul", "beat_sheet.json"), encoding="utf-8"))
    bible = json.load(open(os.path.join(sdir, "series-bible.json"), encoding="utf-8"))
    clean = at.check(sheet, sdir)
    assert clean["problems"] == [] and clean["untraced_beats"] == [] and clean["cue_file"]
    del sheet["beats"][0]["choreo"]["points"]
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    import dialogue_check as dc
    dc.write_estimate(str(ep), bible)
    monkeypatch.setenv("AHOS_ALLOW_ESTIMATED_VOICE", "1")
    monkeypatch.setattr(rw.sp, "plan", lambda *a, **k: pytest.fail("kapı planlayıcıdan sonra kaldı"))
    res = rw.run(str(ep), bible, 0.0, 8.0, sdir)
    assert res["status"] == "BLOCKED" and res["error"] == "EYLEM_VERIYE_BAGLANMAMIS"
    assert "METIN_EYLEMI_IZSIZ" in res["problems"][0]
    assert json.load(open(ep / "render" / "action_trace.json", encoding="utf-8"))["problems"]
