"""Büyük boy farkında el değiştirme: gerçek çömelme + iki ayrı kavrama noktası. Tamamen sentetik projeler; proje dosyası okunmaz."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import puppet2d as pp  # noqa: E402
import readability as rd  # noqa: E402
import render2d as r2  # noqa: E402
import scenes2d as sc  # noqa: E402
import shot_planner as sp  # noqa: E402


def design(h, age):
    return pp.derive_design({"id": f"k{int(h * 100)}", "age": age}, {"height_m": h})


# ---------------------------------------------------------------- geometri
def test_only_the_higher_shoulder_kneels_and_similar_heights_do_not():
    adult, child, adult2 = design(1.9, 40), design(0.98, 6), design(1.75, 38)
    a, b = pp.kneel_drops(adult, child)
    assert a > 0.25 and b == 0.0
    assert pp.kneel_drops(child, adult) == (b, a)
    assert pp.kneel_drops(adult, adult2) == (0.0, 0.0)
    assert a <= pp.CROUCH_MAX_K * 1.9 * pp.LEG_K["adult"] + 1e-9


def test_kneel_amount_has_no_threshold_step():
    short = design(1.0, 30)
    drops = [pp.kneel_drops(design(1.0 + 0.01 * i, 30), short)[0] for i in range(0, 91)]
    assert drops[0] == 0.0 and drops[-1] > 0.15
    assert max(abs(b - a) for a, b in zip(drops, drops[1:])) < 0.02


@pytest.mark.parametrize("view", ["front", "side"])
def test_shoulder_and_hand_follow_the_same_crouch(view):
    d = design(1.8, 35)
    up = {"x": 0.0, "z": 0.0, "yaw": 0.8 if view == "side" else 0.0, "lean": 0.0, "sq": 1.0, "view": view, "aL": [0.0, 0.2], "aR": [0.0, -0.2]}
    down = dict(up, crouch=0.3)
    for side in "LR":
        assert pp.shoulder_offset(d, up, side)[1] - pp.shoulder_offset(d, down, side)[1] == pytest.approx(0.3)
        (x0, h0), (x1, h1) = pp.hand_offset(d, up, side), pp.hand_offset(d, down, side)
        assert x1 == pytest.approx(x0) and h0 - h1 == pytest.approx(0.3)


@pytest.mark.parametrize("view", ["front", "side"])
@pytest.mark.parametrize("wear", ["pants", "shorts", "skirt"])
def test_drawing_lowers_the_head_and_keeps_the_feet_on_the_ground(view, wear):
    d = dict(design(1.8, 35), lowerwear=wear)
    base = {"x": 0.0, "z": 0.0, "yaw": 0.8 if view == "side" else 0.0, "lean": 0.0, "sq": 1.0, "view": view,
            "head": [0.0, 0.0, 0.0], "aL": [0.0, 0.1], "aR": [0.0, -0.1], "lL": 0.0, "lR": 0.0}
    st = {"mouth": "X", "blink": 0, "emotion": "neutral", "gaze": 0.0, "brow": 0.0, "pulse": 0.0}
    cam = sc.Cam(0.0, 0.9, 1.2)
    box = lambda p: rd._mask(lambda cv, cm: pp.draw_character(cv, d, p, st, cm.x(0.0), cm.y(0.0), cm.s, 0.0), cam).getbbox()
    a, b = box(base), box(dict(base, crouch=0.35))
    assert b[1] - a[1] == pytest.approx(0.35 * cam.s, abs=6)        # baş çömelme kadar alçalır
    assert abs(b[3] - a[3]) <= 3                                    # ayak/gölge yerinde


def test_grip_points_are_distinct_bounded_and_front_hand_is_on_top():
    tall, short = design(1.9, 40), design(0.98, 6)
    a, b = pp.grip_points(tall, (1.0, 0.8), short, (0.0, 0.55))
    assert b[1] > a[1] and b[0] == a[0]                             # kısa olan (önde çizilen) üstte
    assert b[1] - a[1] == pytest.approx(pp.HAND_R_K * (1.9 + 0.98))
    a, b = pp.grip_points(tall, (1.0, 0.8), short, (0.0, 0.55), span=0.05)
    assert b[1] - a[1] == pytest.approx(0.05)                       # küçük nesne: iki el de nesnede kalır


# ---------------------------------------------------------------- planlayıcı + çizim
# (veren, alan, veren boyu, alan boyu, verenin x'i, alanın işareti)
CONFIGS = {
    "cocuk_buyuge_saga": ("nil", "baba", 0.98, 1.9, -0.4, 0.9),
    "buyuk_cocuga_sola": ("dede", "efe", 1.75, 1.1, 0.5, -0.6),
    "yakin_boylar": ("ada", "can", 1.2, 1.35, -0.4, 0.7),
}


def project(tmp_path, name, beat_s=7.0, start=2.0, end=3.4):
    giver, taker, h1, h2, gx, tx = CONFIGS[name]
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": name, "characters": [{"id": giver, "name": giver, "age": 6 if h1 < 1.3 else 40}, {"id": taker, "name": taker, "age": 6 if h2 < 1.3 else 40}]}
    for cid, h in ((giver, h1), (taker, h2)):
        json.dump({"height_m": h}, open(root / "assets" / f"{cid}.spec.json", "w"))
    json.dump({}, open(root / "locations.json", "w"))
    json.dump(bible, open(root / "series-bible.json", "w"))
    beat = {"t_start": 0, "t_end": beat_s, "scene_id": "S1", "shot_id": "p1", "location": "", "characters": [giver, taker], "action": "", "camera": "orta",
            "choreo": {"motion": {giver: {"kind": "idle", "x0": gx}, taker: {"kind": "idle", "x0": tx}},
                       "objects": [{"prop": "bottle", "track": [{"t": 0, "holder": giver}, {"t": start, "holder": giver}, {"t": end, "holder": taker}]}]}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    plan = sp.plan(str(ep), bible, str(root / "assets"), 0, beat_s)
    return plan, pp.designs_for(bible, str(root / "assets"))


def handoff(plan, des):
    return next(r for r in rd.measure_plan(plan, des) if r["event"] == "handoff")


def items_at(plan, des, lt):
    tr = {}
    r2.frame(plan, des, plan["beats"][0]["t_start"] + lt, trace=tr)
    return {i[0]: i for i in tr["items"]}


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_handoff_is_readable_in_independent_projects(tmp_path, name):
    plan, des = project(tmp_path, name)
    assert not [n for n in plan["beats"][0]["staging_notes"] if n["kind"] == "conflict"]
    assert not r2.handoff_problems(plan, des)
    r = handoff(plan, des)
    assert r["ok"], r["fails"]


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_drawn_hands_reach_their_grip_points(tmp_path, name):
    """Ön kontrolün 'yetişir' dediği temasta ÇİZİLEN iki el aynı dikey çizgide, iki ayrı yükseklikte buluşur."""
    plan, des = project(tmp_path, name)
    giver, taker = CONFIGS[name][:2]
    it = items_at(plan, des, 2.6)                                   # kollar tam uzanmış aralık
    pos = {}
    for c in (giver, taker):
        _c, d, p, *_ = it[c]
        dx, h = pp.hand_offset(d, p, r2.pick_hand(plan["beats"][0], c))
        pos[c] = (p["x"] + dx, h)
    split = pos[giver][1] - pos[taker][1]
    assert abs(pos[giver][0] - pos[taker][0]) < 0.07, pos
    assert 0.03 < abs(split) <= 0.26, pos                          # üst üste binmez; şişenin kavranabilir boyu içinde


def test_kneel_is_smooth_starts_after_walking_and_ends_standing(tmp_path):
    plan, des = project(tmp_path, "cocuk_buyuge_saga")
    b = plan["beats"][0]; taker = "baba"
    series = []
    for k in range(int(7.0 * 24)):
        it = items_at(plan, des, k / 24)
        series.append((k / 24, it[taker][2].get("crouch", 0.0), it["nil"][2].get("crouch", 0.0)))
    assert max(c for _t, c, _o in series) > 0.3 and all(o == 0.0 for *_x, o in series)
    assert series[0][1] == 0.0 and series[-1][1] == 0.0             # plan sınırında ayakta: kesmede poz sıçraması yok
    assert max(abs(b_[1] - a_[1]) for a_, b_ in zip(series, series[1:])) < 0.07       # 24 fps'te kare başına < 7 cm
    walk_end = r2._walk_end(b["motion"][taker], 7.0)
    assert walk_end > 0 and all(c == 0.0 for t, c, _o in series if t <= walk_end - 1e-6), walk_end


def test_late_walk_still_gets_minimum_kneel_time_within_the_beat():
    beat = {"t_start": 0, "t_end": 3.0, "motion": {"a": {"kind": "walk", "x0": 0, "x1": 1, "walk_s": 3.0}, "b": {"kind": "idle", "x0": 2}}}
    a, b, c, d = r2.crouch_times(beat, {"by": "a", "to": "b", "t_start": 1.0, "t": 2.0})
    assert a >= 0 and b - a >= r2.CROUCH_MIN_S - 1e-9 and d - c >= r2.CROUCH_MIN_S - 1e-9


# ---------------------------------------------------------------- bilerek eklenen hata
def test_without_kneeling_the_big_height_difference_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "kneel_drops", lambda a, b: (0.0, 0.0))
    plan, des = project(tmp_path, "cocuk_buyuge_saga")
    conflicts = [n for n in plan["beats"][0]["staging_notes"] if n["kind"] == "conflict"]
    assert conflicts or r2.handoff_problems(plan, des) or not handoff(plan, des)["ok"]


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_both_hands_stay_visible_through_the_whole_handoff(tmp_path, name):
    """Önde çizilen karakterin saçı/kolu arkadaki elin üstüne binse de alıcı ve verici el HER örnekte görünür (yalnız oran değil, en kötü an)."""
    plan, des = project(tmp_path, name)
    r = handoff(plan, des)
    giver, taker = CONFIGS[name][:2]
    for c in (giver, taker):
        assert r["metrics"][f"hand:{c}"]["min"] >= 0.6, r["metrics"]


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_transfer_draws_the_fingers_of_both_participants_on_top(tmp_path, name):
    plan, des = project(tmp_path, name)
    giver, taker = CONFIGS[name][:2]
    tr = {}; r2.frame(plan, des, plan["beats"][0]["t_start"] + 2.7, trace=tr)
    order = [(k, key) for k, key, *_ in tr["layers"]]
    grips = [key for k, key in order if k == "grip"]
    assert sorted(grips) == sorted([giver, taker]), order
    obj = order.index(("object", "bottle"))
    assert all(order.index(("grip", c)) > obj for c in (giver, taker))
