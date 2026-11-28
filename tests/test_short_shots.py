"""K1e: kamera katmanlarının birleşimi anlık plan kırıntısı bırakamaz (aksiyon/gösterme kadrajı, tepki planı, vuruş kenarı). İki sentetik proje."""
import json
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import readability  # noqa: E402
import render2d as r2  # noqa: E402
import shot_cuts  # noqa: E402
import shot_planner as sp  # noqa: E402
from test_listener_reaction import PROJECTS, make_project  # noqa: E402

DUR = 9.0
PICK_T0, PICK_T1 = 3.0, 4.2                       # nesne bu aralıkta alınır: sabit kadraj 2,4-4,8 sn


def scene(tmp_path, name, lines, camera="geniş", start=PICK_T0, end=PICK_T1):
    """lines: [(konuşan sırası, başlangıç, süre)]."""
    _plan, designs = make_project(tmp_path, name, ["a"])
    root = tmp_path / name
    ids = [c[0] for c in PROJECTS[name]]
    tall = max(ids, key=lambda c: designs[c]["height"])
    other = next(c for c in ids if c != tall)
    sheet = {"beats": [{"t_start": 0, "t_end": DUR, "characters": [tall, other], "camera": camera, "location": "yer", "action": "Alır.",
                        "choreo": {"motion": {tall: {"kind": "idle", "x0": -0.9}, other: {"kind": "idle", "x0": 0.9}},
                                   "objects": [{"prop": "bottle", "track": [{"t": 0, "at": [-0.9, 0.0]}, {"t": start, "at": [-0.9, 0.0]},
                                                                            {"t": end, "holder": tall}, {"t": DUR, "holder": tall}]}]}}]}
    (root / "ep" / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    items = [{"beat": 0, "char": (tall, other)[who], "text": "Bak şuna!", "start_s": a, "duration_s": d} for who, a, d in lines]
    (root / "ep" / "voice_manifest.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    bible = {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]}
    return sp.plan(str(root / "ep"), bible, str(root / "assets"), 0, DUR), designs


def no_dissolve(segs, _min_s):
    return shot_cuts._join_equal(segs)


@pytest.mark.parametrize("name", sorted(PROJECTS))
@pytest.mark.parametrize("gap", [0.15, 0.3, 0.5])
def test_reaction_starting_just_after_the_action_shot_leaves_no_fragment(tmp_path, name, gap, monkeypatch):
    lines = [(0, 3.0, 4.8 + gap - 3.0)]                        # replik sabit kadraj bittikten 'gap' sn sonra biter: tepki o an başlar
    plan, designs = scene(tmp_path / "fixed", name, lines)
    assert readability.short_shots(plan, designs) == []
    assert readability.camera_pops(plan, designs) == []
    monkeypatch.setattr(shot_cuts, "dissolve_crumbs", no_dissolve)     # bozma: eski davranış
    caught = readability.short_shots(plan, designs)
    assert [c for c in caught if abs(c["t0"] - 4.8) < 0.1 and c["t1"] - c["t0"] == pytest.approx(gap, abs=0.09)], caught
    assert readability.short_shot_problems(caught)[0]["rule"] == "SHOT_FLASH"


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_action_shot_that_would_start_just_after_the_beat_starts_at_the_beat(tmp_path, name, monkeypatch):
    plan, designs = scene(tmp_path, name, [], start=0.9, end=2.2)             # kadraj 0,3 sn'de kurulacaktı
    assert r2.camera_choice(plan, plan["beats"][0], 0.0)[0] == "action"
    monkeypatch.setattr(shot_cuts, "dissolve_crumbs", no_dissolve)
    assert r2.camera_choice(plan, plan["beats"][0], 0.0)[0] != "action"


def seg(key, a, b, bounds=None):
    return {"key": key, "a": a, "b": b, "bounds": bounds, "parts": [(None, a, b)]}


def shape(segs):
    return [(s["key"], round(s["a"], 3), round(s["b"], 3)) for s in shot_cuts.dissolve_crumbs(segs, 0.6)]


def test_dissolve_rules():
    # önceki plan uzar: sıradaki kesme zamanında kalır
    assert shape([seg("a", 0, 2), seg("x", 2, 2.3), seg("b", 2.3, 5)]) == [("a", 0, 2.3), ("b", 2.3, 5)]
    # iki yanı aynı plan: tek plan olur
    assert shape([seg("a", 0, 2), seg("x", 2, 2.3), seg("a", 2.3, 5)]) == [("a", 0, 5)]
    # baştaki kırıntıyı sonraki plan üstlenir
    assert shape([seg("x", 0, 0.3), seg("b", 0.3, 5)]) == [("b", 0, 5)]
    # art arda kırıntılar: hiçbiri kalmaz
    out = shape([seg("a", 0, 2), seg("x", 2, 2.25), seg("y", 2.25, 2.5), seg("z", 2.5, 2.9), seg("b", 2.9, 5)])
    assert all(b - a >= 0.6 - 1e-3 for _k, a, b in out), out
    # sabit kadraj kendi vuruşunun dışına uzamaz: sonraki plan erken başlar
    assert shape([seg("f", 0, 3, (0, 3)), seg("x", 3, 3.3), seg("b", 3.3, 6)]) == [("f", 0, 3), ("b", 3, 6)]
    # kısa sabit kadraj silinmez; serbest komşudan süre alır
    assert shape([seg("a", 0, 2), seg("f", 2, 2.3, (0, 9)), seg("b", 2.3, 5)]) == [("a", 0, 2), ("f", 2, 2.6), ("b", 2.6, 5)]
    # tek plan: dokunulmaz
    assert shape([seg("a", 0, 0.3)]) == [("a", 0, 0.3)]


def random_scene(tmp_path, name, k):
    rng = random.Random(1000 + k)
    t, lines = round(rng.uniform(0.1, 1.5), 2), []
    while True:
        d = round(rng.uniform(0.4, 4.0), 2)
        if t + d > DUR - 0.2:
            break
        lines.append((rng.randrange(2), t, d))
        t = round(t + d + rng.uniform(0.05, 1.6), 2)
    start = round(rng.uniform(0.7, 6.5), 2)
    return scene(tmp_path, name, lines, camera=rng.choice(["geniş", "orta", "yakın"]), start=start, end=round(start + rng.uniform(0.7, 1.6), 2))


def test_thirty_random_dialogue_scenes_have_no_fragment(tmp_path, monkeypatch):
    broken = 0
    for k in range(30):
        name = sorted(PROJECTS)[k % len(PROJECTS)]
        plan, designs = random_scene(tmp_path / str(k), name, k)
        assert readability.short_shots(plan, designs) == [], k
        assert readability.camera_pops(plan, designs) == [], k
        assert readability.reaction_problems(readability.reaction_shots(plan, designs)) == [], k
        with monkeypatch.context() as m:
            m.setattr(shot_cuts, "dissolve_crumbs", no_dissolve)
            broken += bool(readability.short_shots(plan, designs))
    assert broken >= 8, broken                                   # tarama boş değil: eritme kapalıyken aynı sahnelerde kırıntı var


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_a_one_frame_class_fragment_injected_into_the_camera_is_caught(tmp_path, name, monkeypatch):
    """Kapı hangi katmandan geldiğine bakmaz: kurgu kararına zorla sokulan 0,25 sn'lik plan da yakalanır."""
    plan, designs = scene(tmp_path, name, [], start=6.0, end=7.2)
    assert readability.short_shots(plan, designs) == []
    real = r2.chosen_shot

    def flicker(plan_, beat, t):
        out = real(plan_, beat, t)
        return dict(out, preset="close", focus=beat["cast"][0]) if 2.0 <= t < 2.25 else out
    monkeypatch.setattr(r2, "chosen_shot", flicker)
    assert [c for c in readability.short_shots(plan, designs) if c["preset"] == "close" and c["t0"] == pytest.approx(2.0, abs=0.05)]


def continuous_scene(tmp_path, name, k):
    """Aynı mekân ve kadroda art arda dört vuruş (kamera vuruş sınırını aşarak sürer), rastgele replikler."""
    rng = random.Random(5000 + k)
    _plan, designs = make_project(tmp_path, name, ["a"])
    root = tmp_path / name
    ids = [c[0] for c in PROJECTS[name]]
    t, beats, items = 0.0, [], []
    for i in range(4):
        d = rng.choice([2.0, 3.0, 5.0, 7.0, 9.0])
        beats.append({"t_start": t, "t_end": t + d, "characters": ids, "camera": rng.choice(["geniş", "orta", "yakın"]), "location": "yer",
                      "action": "Konuşur.", "choreo": {"motion": {ids[0]: {"kind": "idle", "x0": -0.9}, ids[1]: {"kind": "idle", "x0": 0.9}}}})
        s = round(rng.uniform(0.05, 0.5), 2)
        while s < d - 0.5:
            ld = round(rng.uniform(0.3, 3.8), 2)
            if s + ld > d - 0.05:
                break
            items.append({"beat": i, "char": ids[rng.randrange(2)], "text": "Bak şuna!", "start_s": s, "duration_s": ld})
            s = round(s + ld + rng.uniform(0.03, 1.4), 2)
        t += d
    (root / "ep" / "beat_sheet.json").write_text(json.dumps({"beats": beats}, ensure_ascii=False), encoding="utf-8")
    (root / "ep" / "voice_manifest.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    bible = {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]}

    def make(a, b):
        return sp.plan(str(root / "ep"), bible, str(root / "assets"), a, b)
    return make, designs, beats[2]["t_start"], t


@pytest.mark.parametrize("k", range(4))
def test_continuous_beats_have_no_fragment_and_chunked_production_cuts_the_same(tmp_path, k):
    make, designs, cut, end = continuous_scene(tmp_path, sorted(PROJECTS)[k % 2], k)
    full = make(0, end)
    assert readability.short_shots(full, designs) == []
    assert readability.camera_pops(full, designs) == []
    parts = [make(0, cut), make(cut, end)]                      # parça parça üretim: sınırın iki yanı aynı kurguyu görür
    for j in range(int(end * 12)):
        t, a, b = j / 12.0, {}, {}
        r2.frame(full, designs, t, trace=a, camera_only=True)
        r2.frame(parts[t >= cut], designs, t, trace=b, camera_only=True)
        assert (a["preset"], round(a["cam"].s, 2), round(a["cam"].cx, 3)) == (b["preset"], round(b["cam"].s, 2), round(b["cam"].cx, 3)), t
