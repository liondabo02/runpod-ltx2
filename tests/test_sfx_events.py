import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import numpy as np
import sfx_events as S, object_state as O, music_worker as MW

SHEET = {"beats": [
    {"id": "b1", "t_start": 10.0, "t_end": 20.0, "action": "tutar", "choreo": {"objects": [{"prop": "bottle", "track": [{"t": 0, "at": [-1.3, 0.0]}, {"t": 1.6, "at": [-1.3, 0.0]}, {"t": 2.8, "holder": "aden"}, {"t": 5, "holder": "aden"}]}]}},
    {"id": "b2", "t_start": 20.0, "t_end": 30.0, "action": "verir", "choreo": {"objects": [{"prop": "stone", "track": [{"t": 0, "holder": "aden"}, {"t": 2.0, "holder": "aden"}, {"t": 3.4, "holder": "harun"}, {"t": 6, "holder": "harun"}, {"t": 7, "at": [0.2, 0.0]}]}]}},
    {"id": "b3", "t_start": 30.0, "t_end": 40.0, "action": "atar", "choreo": {"objects": [{"prop": "bottle", "track": [{"t": 0, "holder": "harun"}, {"t": 2.0, "holder": "harun"}, {"t": 3.2, "at": "bin_green", "hide": True}]}]}},
]}

def test_one_cue_per_event_with_absolute_times():
    cues = S.cues_from_beats(SHEET, "ep")
    expected = sum(len(O.events(o["track"])) for b in SHEET["beats"] for o in b["choreo"]["objects"])
    assert len(cues) == expected == 4
    assert [round(c["t"], 1) for c in cues] == [12.8, 23.4, 27.0, 33.2]          # beat başlangıcı + yerel olay zamanı
    assert {c["type"] for c in cues} == {"pickup", "handoff", "drop", "dispose"}
    assert all(c["source"] == "object_state.events" for c in cues)

def test_cue_ids_unique_and_stable_across_runs():
    a = S.cues_from_beats(SHEET, "ep"); b = S.cues_from_beats(SHEET, "ep")
    assert a == b and len({c["id"] for c in a}) == len(a)
    assert S.cues_from_beats(SHEET, "ep2")[0]["id"] != a[0]["id"]          # bölüme özgü kimlik

def test_render_is_deterministic_and_duplicates_are_ignored():
    cues = S.cues_from_beats(SHEET, "ep"); n = int(45 * S.SR)
    x = S.render(cues, n); y = S.render(cues, n); z = S.render(cues + cues, n)          # mükerrer cue listesi = aynı ses
    assert np.array_equal(x, y) and np.array_equal(x, z) and np.abs(x).max() > 0.05

def test_sound_lands_exactly_at_event_time_and_nowhere_else():
    cues = S.cues_from_beats(SHEET, "ep"); x = S.render(cues, int(45 * S.SR))
    for c in cues:
        i0 = int(c["t"] * S.SR); assert np.abs(x[i0:i0 + int(0.05 * S.SR)]).max() > 0.02, c        # olay anında ses var
    # olaysız bir aralık sessiz
    assert np.abs(x[int(14 * S.SR):int(22 * S.SR)]).max() == 0.0

def test_material_and_event_choose_different_sounds():
    assert S.kind_for("dispose", "bottle") == "clunk" and S.kind_for("pickup", "bottle") == "clink" and S.kind_for("drop", "stone") == "thud" and S.kind_for("pickup", "hat") == "tap"

def test_music_worker_run_writes_cues_once_and_rerun_has_same_cues():
    d = tempfile.mkdtemp(); json.dump(SHEET, open(os.path.join(d, "beat_sheet.json"), "w"))
    m1 = MW.run(d, "dizi"); c1 = json.load(open(os.path.join(d, "audio", "sfx_cues.json")))
    m2 = MW.run(d, "dizi"); c2 = json.load(open(os.path.join(d, "audio", "sfx_cues.json")))      # yeniden başlatma
    assert c1 == c2 and c1["count"] == 4 and m1["sfx_cues"] == 4 and "sentez" in c1["provenance"]
    assert open(os.path.join(d, "audio", "bed.wav"), "rb").read() is not None

def test_bed_is_regenerated_when_sheet_changes_and_kept_when_not():
    d = tempfile.mkdtemp(); sp = os.path.join(d, "beat_sheet.json"); json.dump(SHEET, open(sp, "w"))
    assert MW.needs_refresh(d)
    MW.run(d, "dizi"); assert not MW.needs_refresh(d)
    sh2 = json.loads(json.dumps(SHEET)); sh2["beats"][0]["choreo"]["objects"][0]["track"][2]["t"] = 3.0; json.dump(sh2, open(sp, "w"))
    assert MW.needs_refresh(d)                                           # sahne değişti: eski yatak kullanılmaz
    MW.run(d, "dizi"); assert json.load(open(os.path.join(d, "audio", "sfx_cues.json")))["cues"][0]["t"] == 13.0


def test_verify_bed_accepts_correct_mix_and_catches_shift_duplicate_extra_level():
    cues = S.cues_from_beats(SHEET, "ep"); n = int(45 * S.SR); good = S.render(cues, n)
    assert S.verify_bed(good, cues) == []
    shifted = np.roll(good, int(0.12 * S.SR))                                           # kaymış temas sesi (120 ms geç)
    assert any(p["problem"] == "zaman_kaymis" for p in S.verify_bed(shifted, cues))
    extra = good.copy(); extra[int(15 * S.SR):int(15 * S.SR) + 400] = 0.3               # olaysız yerde fazla ses
    assert any(p["problem"] == "beklenmeyen_ses" for p in S.verify_bed(extra, cues))
    quiet = good * 0.01; assert any(p["problem"] == "seviye" for p in S.verify_bed(quiet, cues))
    loud = good * 40; assert any(p["problem"] in ("seviye", "kirpilma") for p in S.verify_bed(loud, cues))


def test_each_sound_has_right_kind_duration_and_decay_and_restart_adds_nothing():
    cues = S.cues_from_beats(SHEET, "ep")
    dur = {"tap": 0.06, "clink": 0.22, "thud": 0.16, "clunk": 0.28}
    for c in cues:
        w = np.array(S.wave(c["kind"], int(c["id"], 16)))
        assert abs(len(w) / S.SR - dur[c["kind"]]) < 0.005                               # doğru süre
        tail = float(np.sum(w[-len(w) // 10:] ** 2)); head = float(np.sum(w[:len(w) // 2] ** 2)); assert tail < 0.05 * head   # sönümlenir (patlama yok)
    kinds = {c["type"] + ":" + c["prop"]: c["kind"] for c in cues}
    assert kinds["pickup:bottle"] == "clink" and kinds["dispose:bottle"] == "clunk" and kinds["handoff:stone"] in ("thud", "tap", "clink", "clunk")
    n = int(45 * S.SR); once = S.render(cues, n); twice = S.render(cues + cues, n)       # yeniden başlatma/çift ekleme: ses ikilenmez
    assert np.array_equal(once, twice) and float(np.abs(twice).max()) < 0.95
