"""Yakın kadrajlar arası geçiş (K1d) ve dürüst yakın plan (Y2d). İki farklı sentetik proje; proje verisi motorda sabit değildir."""
import json
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import puppet2d as pp  # noqa: E402
import readability  # noqa: E402
import render2d as r2  # noqa: E402
import shot_cuts  # noqa: E402
import shot_planner as sp  # noqa: E402
from test_listener_reaction import PROJECTS, make_project  # noqa: E402

DUR = 9.0


# ---------------------------------------------------------------- saf kural
def test_the_camera_and_the_pop_measure_read_the_same_cut_threshold():
    assert readability.DEFAULTS["cut_zoom_ratio"] == shot_cuts.CUT_ZOOM_RATIO
    assert readability.DEFAULTS["cut_shift_px"] == shot_cuts.CUT_SHIFT_PX
    assert shot_cuts.is_real_cut(1.2, 0, 0) and shot_cuts.is_real_cut(1 / 1.2, 0, 0) and shot_cuts.is_real_cut(1.0, 320, 0)
    assert not shot_cuts.is_real_cut(1.19, 319, 179)


def test_every_joinable_pair_moves_below_the_pop_limit_per_frame():
    """Gerçek kesme olmayan her kadraj farkı için geçişin kare başı tepe adımı atlama ölçüsünün sınırlarının altında kalır."""
    zmax = shot_cuts.CUT_ZOOM_RATIO * shot_cuts.JOIN_MARGIN[0]
    px = shot_cuts.CUT_SHIFT_PX[0] * shot_cuts.JOIN_MARGIN[1]
    for zr in (1.0, 1.01, 1.05, 1.19, zmax, 1 / zmax, 0.9):
        for shift in (0.0, 40.0, 183.0, px):
            sec = shot_cuts.soft_seconds(zr, shift, 0.0)
            assert shot_cuts.SOFT_MIN_S <= sec <= shot_cuts.SOFT_MAX_S
            n = sec * 12
            eased = [r2.pp_smooth(min(1.0, k / n)) for k in range(int(n) + 3)]
            step = max(b - a for a, b in zip(eased, eased[1:]))
            assert abs(math.exp(step * math.log(zr)) - 1.0) <= readability.DEFAULTS["pop_zoom_step"], (zr, shift)
            second = max(abs(c - 2 * b + a) for a, b, c in zip([0.0] + eased, eased, eased[1:]))
            assert second * shift <= readability.DEFAULTS["pop_jerk_px"], (zr, shift)


# ---------------------------------------------------------------- gerçek kare yolu
def scene(tmp_path, name, objects, camera="orta", xs=(-0.9, 0.9), tall_holds=False):
    """Tek uzun vuruş; objects(kısa, uzun) -> nesne izleri."""
    _plan, designs = make_project(tmp_path, name, ["Bugün hava güzel."])
    root = tmp_path / name
    ids = [c[0] for c in PROJECTS[name]]
    tall = max(ids, key=lambda c: designs[c]["height"])
    other = next(c for c in ids if c != tall)
    sheet = {"beats": [{"t_start": 0, "t_end": DUR, "characters": [tall, other], "camera": camera, "location": "yer", "action": "Dururlar.",
                        "choreo": {"motion": {tall: {"kind": "idle", "x0": xs[0]}, other: {"kind": "idle", "x0": xs[1]}},
                                   "objects": objects(tall, other)}}]}
    (root / "ep" / "beat_sheet.json").write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    (root / "ep" / "voice_manifest.json").write_text(json.dumps({"items": []}), encoding="utf-8")
    bible = {"id": name, "characters": [{"id": c, "name": c.title(), "role": r, "age": g} for c, r, g, _h in PROJECTS[name]]}

    def planned(t0=0, t1=DUR):
        return sp.plan(str(root / "ep"), bible, str(root / "assets"), t0, t1)
    return planned, designs, tall


def ground_pickup(tall, _other):
    """Uzun oyuncu 3,0-4,2 sn arasında yerden küçük bir nesne alır: grup planının içine aksiyon kadrajı girer ve çıkar."""
    return [{"prop": "bottle", "track": [{"t": 0, "at": [-0.9, 0.0]}, {"t": 3.0, "at": [-0.9, 0.0]}, {"t": 4.2, "holder": tall}, {"t": DUR, "holder": tall}]}]


def framing_at(plan, designs, t):
    tr = {}
    r2.frame(plan, designs, t, trace=tr, camera_only=True)
    return tr


def raw_only(plan, designs, beat, t, items, _memo=None):
    """Bilerek bozma: geçiş yok, her kural kendi kadrajına tek karede atlar (eski davranış)."""
    return dict(r2.camera_raw(plan, designs, beat, t, items), soft=None)


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_action_framing_next_to_a_group_shot_moves_continuously_and_removing_the_join_is_caught(tmp_path, name, monkeypatch):
    planned, designs, _tall = scene(tmp_path, name, ground_pickup, camera="geniş")
    plan = planned()
    assert r2.action_staging.hold_windows(plan["beats"][0])
    assert readability.camera_pops(plan, designs) == []
    assert any(framing_at(plan, designs, k / 12)["soft"] is not None for k in range(int(DUR * 12)))
    monkeypatch.setattr(r2, "soft_camera", raw_only)
    pops = readability.camera_pops(plan, designs)
    assert [p for p in pops if p["kind"] == "framing"], pops
    assert readability.camera_pop_problems(pops), "yakın-ama-farklı kadraj atlaması artık üretimi durdurmalı"


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_join_that_crosses_a_chunk_edge_is_identical_and_needs_the_neighbour_data(tmp_path, name):
    """Parça parça üretim: aksiyon kadrajından çıkış geçişi vuruş sınırını aşarken pencere o sınırda başlasa da aynı kadraj çıkar."""
    def pickup(tall, _other):                                            # aksiyon kadrajı 4,8 sn'de biter, vuruş 5,0 sn'de
        return [{"prop": "bottle", "track": [{"t": 0, "at": [-0.9, 0.0]}, {"t": 3.0, "at": [-0.9, 0.0]}, {"t": 4.2, "holder": tall}, {"t": 5.0, "holder": tall}]}]
    planned, designs, tall = scene(tmp_path, name, pickup, camera="geniş")
    sheet_path = tmp_path / name / "ep" / "beat_sheet.json"
    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
    first = sheet["beats"][0]
    first.update(t_end=5.0, scene_id="S")
    second = dict(first, t_start=5.0, t_end=DUR, choreo={"motion": first["choreo"]["motion"], "objects": [{"prop": "bottle", "track": [{"t": 0, "holder": tall}, {"t": 4.0, "holder": tall}]}]})
    sheet["beats"] = [first, second]
    sheet_path.write_text(json.dumps(sheet, ensure_ascii=False), encoding="utf-8")
    whole, part = planned(), planned(5, DUR)
    assert shot_cuts.continues(whole["beats"][0], whole["beats"][1]) and len(part["beats"]) == 1 and part["context"]
    want = framing_at(whole, designs, 5.05)
    assert want["soft"] is not None
    got = framing_at(part, designs, 5.05)["cam"]
    assert (got.cx, got.cy, got.s) == pytest.approx((want["cam"].cx, want["cam"].cy, want["cam"].s))
    lone = framing_at(dict(part, context=[]), designs, 5.05)["cam"]       # bozma: komşu verisi yoksa parça geçişi bilmez
    assert abs(lone.cy - want["cam"].cy) + abs(lone.cx - want["cam"].cx) + abs(lone.z - want["cam"].z) > 0.005
    assert readability.camera_pops(whole, designs) == []


def held_low(tall, _other):
    return [{"prop": "shovel", "track": [{"t": 0, "holder": tall}, {"t": DUR, "holder": tall}]}]


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_close_shot_that_must_open_to_full_body_is_called_medium(tmp_path, name, monkeypatch):
    """Y2d: alçakta tutulan konu nesnesi yakın planı iki kişilik boy plana açıyorsa plan 'orta' adını alır ve gerçek orta kadraj çizilir."""
    planned, designs, tall = scene(tmp_path, name, held_low, camera="yakın plan", xs=(-0.5, 0.5))
    plan = planned()
    beat = plan["beats"][0]
    assert beat["camera"] == "close" and beat["focus"] in beat["cast"]
    beat["focus"] = tall
    assert r2.shot_needs(plan, designs, tall, [(beat, 0.0, 2.0)])["held"] < r2.hip_height(designs[tall])
    tr = framing_at(plan, designs, 1.0)
    assert (tr["preset"], tr["opened_from"]) == ("medium", "close")
    assert sorted(tr["drawn"]) == sorted(beat["cast"])
    assert not [v for v in readability.measure_crop(plan, designs)["violations"] if v["rule"] == "YAKIN_PLAN_YAKIN_DEGIL"]
    monkeypatch.setattr(r2, "close_tightness", lambda *a, **k: (9.9, "full"))     # bozma: eski davranış, adı 'yakın' kalan boy plan
    assert framing_at(plan, designs, 1.0)["preset"] == "close"
    caught = [v for v in readability.measure_crop(plan, designs)["violations"] if v["rule"] == "YAKIN_PLAN_YAKIN_DEGIL"]
    assert caught and caught[0]["who"] == tall and readability.crop_problems({"violations": caught})[0]["rule"] == "YAKIN_PLAN_YAKIN_DEGIL"


@pytest.mark.parametrize("name", sorted(PROJECTS))
def test_ordinary_close_shot_stays_close(tmp_path, name):
    planned, designs, tall = scene(tmp_path, name, lambda *_a: [], camera="yakın plan")
    plan = planned()
    plan["beats"][0]["focus"] = tall
    tr = framing_at(plan, designs, 1.0)
    assert (tr["preset"], tr["opened_from"]) == ("close", None)
    group = r2.group_framing(plan["beats"][0], designs, [i[2]["x"] for i in tr["items"]], "medium", 0.0)[2]
    assert tr["cam"].z / group >= shot_cuts.CUT_ZOOM_RATIO
