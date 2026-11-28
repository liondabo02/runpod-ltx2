"""Gösterme jesti (K1c): hedef veride taşınır; kamera, kol, bloklama ve ölçü aynı veriyi okur. İki farklı sentetik proje."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import pointing  # noqa: E402
import puppet2d as pp  # noqa: E402
import readability  # noqa: E402
import render2d as r2  # noqa: E402
import shot_motion as sm  # noqa: E402
import shot_planner as sp  # noqa: E402
from test_listener_reaction import PROJECTS, make_project  # noqa: E402

DUR = 8.0


def scene(tmp_path, name, xs=(0.7, -0.5), points=None, camera="yakın plan", voice=True, prop_x=-1.7):
    """İlk oyuncu (gösteren) yerdeki nesneyi gösterir; ikinci oyuncu xs[1]'de durur. Gösteren projedeki UZUN oyuncudur."""
    _plan, designs = make_project(tmp_path, name, ["Bak, yerde bir şey var!"])
    root = tmp_path / name
    ids = sorted((c[0] for c in PROJECTS[name]), key=lambda c: -designs[c]["height"])
    tall, other = ids
    if points is None:
        points = [{"by": tall, "to": {"prop": "bottle"}, "line": 0, "t": 4.0, "dur": 2.0}]
    sheet = {"beats": [{"t_start": 0, "t_end": DUR, "characters": [tall, other], "camera": camera, "location": "yer", "action": "Biri yeri gösterir.",
                        "choreo": {"motion": {tall: {"kind": "idle", "x0": xs[0]}, other: {"kind": "idle", "x0": xs[1]}},
                                   "objects": [{"prop": "bottle", "track": [{"t": 0, "at": [prop_x, 0.0]}, {"t": DUR, "at": [prop_x, 0.0]}]}],
                                   "points": points}}]}
    (root / "ep" / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    items = [{"beat": 0, "char": tall, "text": "Bak, yerde bir şey var!", "duration_s": 2.0, "start_s": 1.0}] if voice else []
    (root / "ep" / "voice_manifest.json").write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
    bible = {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]}
    return sp.plan(str(root / "ep"), bible, str(root / "assets"), 0, DUR), designs, tall, other


def rules(plan, designs):
    return {p["rule"] for p in readability.pointing_problems(readability.measure_pointing(plan, designs))}


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_pointed_object_is_framed_aimed_at_and_the_camera_moves_without_pops(tmp_path, name):
    plan, designs, tall, _other = scene(tmp_path, name)
    report = readability.measure_pointing(plan, designs)
    assert readability.pointing_problems(report) == [], report
    assert report[0]["samples"] >= 8
    tr = {}
    r2.frame(plan, designs, 2.0, trace=tr, camera_only=True)
    assert tr["preset"] == "point"
    tr = {}
    r2.frame(plan, designs, 6.0, trace=tr, camera_only=True)
    assert tr["preset"] != "point"                              # jest bitince yönetmenin planı geri gelir
    assert readability.camera_pops(plan, designs) == []


def test_gesture_follows_the_speakers_line_and_falls_back_to_its_own_time(tmp_path):
    plan, _d, _tall, _o = scene(tmp_path, "kisa_uzun")
    assert pointing.span(plan["beats"][0], pointing.items(plan["beats"][0])[0]) == pytest.approx((1.0, 3.0))
    silent, _d, _tall, _o = scene(tmp_path / "s", "kisa_uzun", voice=False)
    assert pointing.span(silent["beats"][0], pointing.items(silent["beats"][0])[0]) == pytest.approx((4.0, 6.0))


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_removing_the_point_framing_is_caught(tmp_path, name, monkeypatch):
    plan, designs, tall, _o = scene(tmp_path, name)
    plan["beats"][0]["focus"] = tall
    monkeypatch.setattr(r2.pointing, "window_at", lambda *a: None)       # eski davranış: jest sırasında konuşana yakın plan
    monkeypatch.setattr(r2.pointing, "shot_windows", lambda *a: [])
    assert "JEST_HEDEFI_GORUNMUYOR" in rules(plan, designs)


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_arm_that_does_not_point_at_the_target_is_caught(tmp_path, name, monkeypatch):
    plan, designs, _tall, _o = scene(tmp_path, name)
    monkeypatch.setattr(r2.pointing, "apply", lambda *a: None)
    assert "JEST_KOLU_HEDEFE_BAKMIYOR" in rules(plan, designs)


def test_blocking_clears_the_pointing_hand_and_without_it_the_measure_catches_the_cover(tmp_path, monkeypatch):
    plan, designs, tall, other = scene(tmp_path / "a", "kisa_uzun", xs=(0.0, -0.45))
    moved = [n for n in plan["beats"][0]["staging_notes"] if n.get("rule") == "blocking" and n.get("kind") == "adjusted"]
    assert moved, plan["beats"][0]["staging_notes"]
    assert pointing.hand_hidden(plan["beats"][0], designs, pointing.items(plan["beats"][0])[0]) == []
    assert rules(plan, designs) == set()
    monkeypatch.setattr(sp.pointing, "clear", lambda *a, **k: [])
    bad, designs, tall, other = scene(tmp_path / "b", "kisa_uzun", xs=(0.0, -0.45))
    assert pointing.hand_hidden(bad["beats"][0], designs, pointing.items(bad["beats"][0])[0]) == [other]
    assert "JEST_KOLU_ORTULU" in rules(bad, designs)


@pytest.mark.parametrize("target", [{"prop": "yok_boyle_nesne"}, "taninmayan_hedef", None])
def test_gesture_without_a_resolvable_target_stops_the_gate(tmp_path, target):
    _p, designs = make_project(tmp_path / "probe", "kisa_uzun", ["a"])
    tall = max(designs, key=lambda c: designs[c]["height"])
    plan, designs, _tall, _o = scene(tmp_path, "kisa_uzun", points=[{"by": tall, "to": target, "t": 1.0, "dur": 2.0}])
    assert rules(plan, designs) == {"JEST_COZULEMEDI"}


def test_gesture_to_the_other_actor_is_measured_too(tmp_path):
    _p, designs = make_project(tmp_path / "probe", "iki_yetiskin", ["a"])
    tall, other = sorted(designs, key=lambda c: -designs[c]["height"])
    plan, designs, _tall, _o = scene(tmp_path, "iki_yetiskin", xs=(0.9, -0.9), points=[{"by": tall, "to": other, "t": 1.0, "dur": 2.0}])
    assert rules(plan, designs) == set()


# ---------------------------------------------------------------- hedefsiz 'gösterme' üretilmez
@pytest.mark.parametrize("height", [0.98, 1.2, 1.9])
@pytest.mark.parametrize("speaking", [False, True])
def test_no_random_pointing_hand_and_idle_arm_never_reads_as_pointing(height, speaking):
    for seed in range(25):
        for k in range(240):
            pose = sm.pose_at("idle", k / 12, 20.0, seed, 0.0, 0.0, height, height * 0.45, speaking=speaking)
            assert pose.get("hand") != "point"
            if not speaking:
                assert abs(pose["aL"][1]) <= pp.REST_ARM_ANG[0] and abs(pose["aR"][1]) <= pp.REST_ARM_ANG[0]
