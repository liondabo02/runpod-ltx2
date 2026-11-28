"""Tepki planı: dinleyenin yüzünde tepki görünür, konuşana bakar, anlık kesme olmaz. İki farklı sentetik proje (proje verisi kodda sabit değil)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import listener_reaction as lr  # noqa: E402
import puppet2d as pp  # noqa: E402
import readability  # noqa: E402
import render2d as r2  # noqa: E402
import shot_planner as sp  # noqa: E402


def line(char, start, end, mood="neutral"):
    return {"char": char, "start": start, "end": end, "mood": mood, "cues": []}


def beat(cast, lines, gaze=None, t_end=12.0):
    return {"cast": cast, "lines": lines, "t_start": 0.0, "t_end": t_end, "choreo": {"gaze": gaze or {}}}


# ---------------------------------------------------------------- zamanlama kuralları (saf)
def test_short_gap_between_lines_does_not_cut_to_listener():
    b = beat(["a", "b"], [line("a", 0.2, 2.0), line("b", 2.3, 4.0)])
    assert not [w for w in lr.windows(b) if w["speaker"] == "a"]              # 0.3 sn boşluk: anlık plan yok
    assert lr.target(b, 2.1) is None


def test_every_window_is_long_enough_and_never_overlaps():
    for gap in (0.1, 0.5, 0.65, 1.0, 2.5):
        for d in (1.0, 3.0, 3.6, 5.5):
            b = beat(["a", "b"], [line("a", 0.2, 0.2 + d), line("b", 0.2 + d + gap, 0.2 + d + gap + 2.0)])
            ws = lr.windows(b)
            assert all(w["t1"] - w["t0"] >= lr.MIN_SHOT_S - 1e-9 for w in ws), (gap, d, ws)
            assert all(x["t1"] <= y["t0"] + 1e-9 for x, y in zip(ws, ws[1:])), (gap, d, ws)
            assert all(not (x["listener"] == y["listener"] and 0 < y["t0"] - x["t1"] < lr.MIN_SHOT_S) for x, y in zip(ws, ws[1:]))


def test_addressee_comes_from_director_gaze():
    b = beat(["a", "b", "c"], [line("a", 0.2, 2.0)], gaze={"a": "c"})
    assert lr.target(b, 2.4) == "c"
    assert lr.target(beat(["a", "b", "c"], [line("a", 0.2, 2.0)]), 2.4) == "b"


def test_action_framing_fragment_shorter_than_minimum_is_not_cut():
    b = beat(["a", "b"], [line("a", 0.2, 2.0)])                                 # pencere 2.0-3.0
    assert lr.camera_windows(b, [(2.3, 4.0)]) == []
    assert lr.camera_windows(b, [(0.0, 2.2)])[0]["t0"] == pytest.approx(2.2)


def test_listener_who_starts_talking_stops_performing():
    b = beat(["a", "b"], [line("a", 0.2, 2.0), line("b", 3.05, 4.0)])
    assert lr.performance(b, "b", 2.8)["emotion"] == "curious"
    assert lr.performance(b, "b", 3.1) is None


def test_expression_starts_after_the_cut_and_follows_the_line_mood():
    for mood, want in (("happy", "happy"), ("surprise", "surprise"), ("sad", "sad"), ("angry", "sad"), ("neutral", "curious")):
        b = beat(["a", "b"], [line("a", 0.2, 2.0, mood)])
        assert lr.performance(b, "b", 2.0)["emotion"] is None
        assert lr.performance(b, "b", 2.6)["emotion"] == want
        assert lr.performance(b, "a", 2.6) is None


# ---------------------------------------------------------------- çizilen kare: iki proje
PROJECTS = {
    "kisa_uzun": [("mino", "kız çocuk", 4, 0.98), ("dede_x", "dede (erkek)", 62, 1.9)],
    "iki_yetiskin": [("lale", "anne (kadın)", 35, 1.68), ("orhan", "baba", 40, 1.82)],
}


def make_project(tmp_path, name, moods_text):
    chars = PROJECTS[name]
    root = tmp_path / name
    (root / "assets").mkdir(parents=True)
    for cid, _r, _a, h in chars:
        (root / "assets" / f"{cid}.spec.json").write_text(json.dumps({"height_m": h}), encoding="utf-8")
    bible = {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": a} for c, r, a, _h in chars]}
    a, b = chars[0][0], chars[1][0]
    ep = root / "ep"; ep.mkdir()
    sheet = {"beats": [{"t_start": 0, "t_end": 14, "characters": [a, b], "camera": "geniş", "location": "bir_yer", "action": "Konuşurlar.",
                        "choreo": {"motion": {a: {"kind": "idle", "x0": -0.8}, b: {"kind": "idle", "x0": 0.8}}}}]}
    (ep / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    items, t = [], 0.3
    for i, text in enumerate(moods_text):
        items.append({"beat": 0, "char": (a, b)[i % 2], "text": text, "duration_s": 2.2, "start_s": t})
        t += 4.0
    (ep / "voice_manifest.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    designs = pp.designs_for(bible, str(root / "assets"))
    return sp.plan(str(ep), bible, str(root / "assets"), 0, 14), designs


TEXTS = ["Bugün hava güzel.", "Aferin sana!", "Nerede kaldı acaba?"]


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_drawn_reaction_shots_show_a_listening_face(tmp_path, name):
    plan, designs = make_project(tmp_path, name, TEXTS)
    shots = readability.reaction_shots(plan, designs)
    assert len(shots) >= 3, shots
    assert readability.reaction_problems(shots) == []
    assert all(s["listener"] != s["speaker"] for s in shots)


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_gate_catches_a_listener_that_does_not_react(tmp_path, name, monkeypatch):
    """Bilerek bozma: dinleyici oyunculuğu kapatılırsa (eski davranış) aynı ölçü boş tepki planını yakalar."""
    plan, designs = make_project(tmp_path, name, TEXTS)
    monkeypatch.setattr(r2.listener_reaction, "performance", lambda *a, **k: None)
    rules = {p["rule"] for p in readability.reaction_problems(readability.reaction_shots(plan, designs))}
    assert "REACTION_NO_EXPRESSION" in rules, rules


def test_gate_catches_a_listener_looking_away(tmp_path, monkeypatch):
    plan, designs = make_project(tmp_path, "kisa_uzun", TEXTS)
    real = lr.performance

    def turned_away(b, cid, t):
        out = real(b, cid, t)
        return out and dict(out, speaker="yok")                # konuşan bulunamaz: bakış rastgele gezinir
    monkeypatch.setattr(r2.listener_reaction, "performance", turned_away)
    monkeypatch.setattr(r2, "_hash", lambda *a: 0.5)           # göz gezdirme ortada: konuşana bakmıyor
    rules = {p["rule"] for p in readability.reaction_problems(readability.reaction_shots(plan, designs))}
    assert "REACTION_NOT_LOOKING" in rules, rules


def test_gate_catches_a_flash_cut(tmp_path, monkeypatch):
    plan, designs = make_project(tmp_path, "iki_yetiskin", TEXTS)
    monkeypatch.setattr(lr, "REACT_AFTER", 0.2)
    monkeypatch.setattr(lr, "MIN_SHOT_S", 0.0)
    shots = readability.reaction_shots(plan, designs)
    monkeypatch.undo()
    assert "REACTION_FLASH" in {p["rule"] for p in readability.reaction_problems(shots)}


def test_render_gate_blocks_an_empty_reaction_shot(tmp_path, monkeypatch):
    import render_worker
    plan, designs = make_project(tmp_path, "iki_yetiskin", TEXTS)
    root = tmp_path / "iki_yetiskin"
    bible = {"id": "iki_yetiskin", "characters": [{"id": c, "name": c.title(), "role": r, "age": a} for c, r, a, _h in PROJECTS["iki_yetiskin"]]}
    monkeypatch.setattr(r2.listener_reaction, "performance", lambda *a, **k: None)
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: pytest.fail("kapı geçilmemeliydi"))
    res = render_worker.run(str(root / "ep"), bible, 0, 14, str(root))
    assert res["status"] == "BLOCKED" and res["error"] == "TEPKI_PLANI_BOS", res
    assert os.path.exists(root / "ep" / "render" / "reaction_shots.json")


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_eyes_stay_open_on_the_reaction_shot(tmp_path, name, monkeypatch):
    plan, designs = make_project(tmp_path, name, TEXTS)
    monkeypatch.setattr(r2, "blink_at", lambda t, seed: True)            # her an göz kırpma istense bile
    for s in readability.reaction_shots(plan, designs):
        for t in (s["t0"], s["sample_t"]):                                # kesmenin ilk karesi dahil
            tr = {}
            r2.frame(plan, designs, t, trace=tr)
            assert tr["states"][s["listener"]]["blink"] is False, (s, t)


def test_exclamation_of_surprise_is_not_read_as_happy():
    import mood_engine
    assert mood_engine.mood_for("Aa! İçinde su var!") == "surprise"
    assert mood_engine.mood_for("Eyvah, döküldü") == "surprise"
    assert mood_engine.mood_for("Aferin sana!") == "happy"
    assert mood_engine.mood_for("Daha neler yapacağız!") == "happy"        # sözcük içindeki 'aa' ünlem sayılmaz
