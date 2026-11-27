"""Kap içine atış: uçuş (ağızdan içeri) ve bundan BAĞIMSIZ çizim ölçüsü. Tamamen sentetik projeler; proje dosyası okunmaz."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import object_state  # noqa: E402
import props2d  # noqa: E402
import puppet2d as pp  # noqa: E402
import readability as rd  # noqa: E402
import render2d as r2  # noqa: E402
import render_worker  # noqa: E402
import setpieces2d  # noqa: E402
import shot_planner as sp  # noqa: E402

# (atan, seyirci, atan boyu, seyirci boyu, kap x, atanın x'i, seyircinin işareti, hedef, nesne)
CONFIGS = {
    "yetiskin_saga": ("dede", "torun", 1.8, 1.0, 1.0, -0.5, -1.6, "bin_green", "bottle"),
    "cocuk_sola": ("zip", "robo", 1.0, 1.5, -1.0, 0.4, 1.5, "bin_green", "bottle"),
    "orta_uzak_kutu": ("ada", "can", 1.4, 1.2, 0.2, -1.5, -2.4, "bin_yellow", "stone"),
}


def project(tmp_path, name, flight=1.2):
    thrower, other, h1, h2, bin_x, tx, mark, target, prop = CONFIGS[name]
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": name, "characters": [{"id": thrower, "name": thrower, "age": 6 if h1 < 1.3 else 40}, {"id": other, "name": other, "age": 6 if h2 < 1.3 else 40}]}
    for cid, h in ((thrower, h1), (other, h2)):
        json.dump({"height_m": h}, open(root / "assets" / f"{cid}.spec.json", "w"))
    json.dump({f"yer_{name}": {"pieces": [["bins", bin_x]]}}, open(root / "locations.json", "w"))
    json.dump(bible, open(root / "series-bible.json", "w"))
    beat = {"t_start": 0, "t_end": 6, "scene_id": "S1", "shot_id": "p1", "location": f"yer_{name}", "characters": [thrower, other], "action": "", "camera": "orta",
            "choreo": {"motion": {thrower: {"kind": "idle", "x0": tx}, other: {"kind": "idle", "x0": mark}},
                       "objects": [{"prop": prop, "track": [{"t": 0, "holder": thrower}, {"t": 2.0, "holder": thrower}, {"t": 2.0 + flight, "at": target, "hide": True}]}]}}
    json.dump({"beats": [beat]}, open(ep / "beat_sheet.json", "w"))
    return root, ep, bible


def planned(tmp_path, name, **kw):
    root, ep, bible = project(tmp_path, name, **kw)
    return sp.plan(str(ep), bible, str(root / "assets"), 0, 6), pp.designs_for(bible, str(root / "assets"))


def entry(plan, des):
    b = plan["beats"][0]
    ev = next(e for e in rd.action_events(b) if e["type"] == "dispose")
    return rd.measure_entry(plan, des, b, ev)


# ---------------------------------------------------------------- uçuş geometrisi
@pytest.mark.parametrize("p0", [(-1.5, 0.35), (-0.9, 1.5), (2.2, 0.6), (0.6, 2.1)])
def test_flight_starts_at_release_crosses_rim_at_mouth_centre_and_ends_inside(p0):
    mouth, h = (0.5, 0.83), 0.3
    pts = [object_state.sink_flight(p0, mouth, h, i / 2000) for i in range(2001)]
    assert pts[0] == pytest.approx(p0)
    assert pts[-1][0] == pytest.approx(0.5) and pts[-1][1] + h < 0.83
    top = max(range(len(pts)), key=lambda i: pts[i][1])
    assert pts[top][1] >= max(p0[1], 0.83) + object_state.SINK_CLEAR_MIN - 1e-6
    cross = next(i for i in range(top, len(pts)) if pts[i][1] <= 0.83)
    assert abs(pts[cross][0] - 0.5) < 0.01                                   # ağız çizgisi tam merkezde geçilir
    assert all(b[1] <= a[1] + 1e-9 for a, b in zip(pts[top:], pts[top + 1:]))     # tepeden sonra yalnız düşer
    assert max(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(pts, pts[1:])) < 0.02


def test_released_object_does_not_follow_the_hand(tmp_path):
    """Bırakmadan sonra el hareket etmeyi sürdürür; nesnenin yolu yalnız bırakma anının eline bağlıdır."""
    plan, des = planned(tmp_path, "yetiskin_saga")
    b = plan["beats"][0]
    rel = r2.poses_at(plan, des, 2.0)
    hx, hy = r2._objects_now(b, rel, 2.0)[0][1:3]
    below, above, _w = props2d.extent("bottle", 0.55)
    p0 = (hx, hy - below)
    g = setpieces2d.mouth_of("bin_green"); mouth = (b["targets"]["bin_green"][0], g["rim"])
    for lt in (2.15, 2.45, 2.9):
        _o, x, y, _st, own, hand = r2._objects_now(b, r2.poses_at(plan, des, lt), lt, lambda t: r2.poses_at(plan, des, t))[0]
        fx, fy = object_state.sink_flight(p0, mouth, below + above, (lt - 2.0) / 1.2, edge=g["half"] + _w + r2.SINK_WALL_PAD)
        assert (x, y) == pytest.approx((fx, fy + below))
        assert own is None and hand is None


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_hand_does_not_overtake_the_released_object(tmp_path, name):
    """Bırakma anında kol savurması tepededir: sonraki karelerde el, nesnenin atış yönünde önüne geçmez."""
    plan, des = planned(tmp_path, name)
    b = plan["beats"][0]; thrower = CONFIGS[name][0]
    track = b["choreo"]["objects"][0]["track"]
    dirn = 1.0 if b["targets"][CONFIGS[name][7]][0] >= CONFIGS[name][5] else -1.0
    for k in range(1, 7):
        lt = track[1]["t"] + k / 24
        its = r2.poses_at(plan, des, lt)
        _o, x, _y, *_ = r2._objects_now(b, its, lt, lambda t: r2.poses_at(plan, des, t))[0]
        _c, d, p, *_r = next(i for i in its if i[0] == thrower)
        hx = p["x"] + pp.hand_offset(d, p, r2.pick_hand(b, thrower))[0]
        assert dirn * (x - hx) > -0.04, (k, x, hx)


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_independent_projects_enter_through_the_mouth(tmp_path, name):
    plan, des = planned(tmp_path, name)
    m, why = entry(plan, des)
    assert not why, (why, m)
    assert m["crossed_from_above"] and m["last_visible"] < 0.65


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_whole_readability_gate_passes(tmp_path, name):
    plan, des = planned(tmp_path, name)
    bad = [f for r in rd.measure_plan(plan, des) for f in r["fails"]]
    assert not bad, bad


def test_low_release_rises_above_the_rim_before_reaching_the_container_wall():
    mouth, edge = (0.5, 0.83), 0.36
    pts = [object_state.sink_flight((0.0, 0.3), mouth, 0.3, i / 2000, edge=edge) for i in range(2001)]
    first_in = next(p for p in pts if p[0] >= 0.5 - edge + 1e-6)
    assert first_in[1] >= 0.83 - 1e-6 and pts[-1][0] == pytest.approx(0.5)
    assert max(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(pts, pts[1:])) < 0.02


@pytest.mark.parametrize("h,prop", [(0.9, "bottle"), (1.4, "shovel")])
def test_low_release_beside_the_container_is_not_drawn_in_front_of_it(tmp_path, h, prop):
    """Matriste bulunan hata: alçak elden atışta nesne yükselirken kabın önünden geçiyordu."""
    CONFIGS["alcak"] = ("a", "b", h, 1.2, 1.0, -0.5, -1.8, "bin_green", prop)
    try:
        plan, des = planned(tmp_path, "alcak")
        m, why = entry(plan, des)
    finally:
        del CONFIGS["alcak"]
    assert not why, (why, m)


# ---------------------------------------------------------------- bilerek eklenen hatalar (her biri ölçüye takılmalı)
def old_motion(monkeypatch):
    """Önceki motor: kutunun üstündeki hedef noktaya yumuşak geçiş, ağız arkasında kaybolma yok."""
    real = object_state.position
    monkeypatch.setattr(object_state, "position", lambda *a, sink_fn=None, **k: real(*a, **k))
    monkeypatch.setattr(r2, "_entry_target", lambda *a: None)


def test_old_vanish_in_mid_air_is_caught(tmp_path, monkeypatch):
    old_motion(monkeypatch)
    plan, des = planned(tmp_path, "yetiskin_saga")
    m, why = entry(plan, des)
    assert any("birden yok oluyor" in w for w in why) and m["last_visible"] > 0.9, (why, m)
    assert any("yukarıdan" in w for w in why), why


def warped(monkeypatch, fn):
    real = object_state.sink_flight
    monkeypatch.setattr(object_state, "sink_flight", lambda p0, mouth, h, u, edge=0.0: fn(lambda *a: real(*a, edge=edge), p0, mouth, h, u))


@pytest.mark.parametrize("dx", [-0.5, 0.45])
def test_deliberate_miss_is_caught(tmp_path, monkeypatch, dx):
    warped(monkeypatch, lambda real, p0, mouth, h, u: real(p0, (mouth[0] + dx, mouth[1]), h, u))
    plan, des = planned(tmp_path, "yetiskin_saga")
    _m, why = entry(plan, des)
    assert why and any("açıklığın" in w or "önünde" in w for w in why), why


def test_object_drawn_in_front_of_the_container_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(r2, "_clip_above", lambda cv, cam, y, draw: draw(cv, cam))
    plan, des = planned(tmp_path, "yetiskin_saga")
    m, why = entry(plan, des)
    assert any("kabın önünde" in w for w in why) and m["below_rim_m"] > 0.15, (why, m)


def test_flight_that_stops_above_the_rim_is_caught(tmp_path, monkeypatch):
    warped(monkeypatch, lambda real, p0, mouth, h, u: (real(p0, mouth, h, u)[0], max(real(p0, mouth, h, u)[1], mouth[1] + 0.12) if u > 0.5 else real(p0, mouth, h, u)[1]))
    plan, des = planned(tmp_path, "yetiskin_saga")
    _m, why = entry(plan, des)
    assert any("havada" in w for w in why), why


def test_teleport_into_the_mouth_is_caught(tmp_path, monkeypatch):
    warped(monkeypatch, lambda real, p0, mouth, h, u: p0 if u < 0.7 else real(p0, mouth, h, u))
    plan, des = planned(tmp_path, "yetiskin_saga")
    _m, why = entry(plan, des)
    assert any("sıçrama" in w for w in why), why


def test_mid_flight_disappearance_is_caught(tmp_path, monkeypatch):
    plan, des = planned(tmp_path, "yetiskin_saga")
    real = r2._objects_now
    monkeypatch.setattr(r2, "_objects_now", lambda beat, items, lt, items_at=None: [] if 2.4 < lt < 2.6 else real(beat, items, lt, items_at))
    _m, why = entry(plan, des)
    assert any("uçuş ortasında" in w for w in why), why


def test_container_without_mouth_geometry_is_not_silently_passed(tmp_path, monkeypatch):
    plan, des = planned(tmp_path, "yetiskin_saga")
    monkeypatch.setattr(setpieces2d, "MOUTHS", {})
    _m, why = entry(plan, des)
    assert why and "ölçülemez" in why[0]


def test_render_gate_blocks_a_miss_and_names_the_engine(tmp_path, monkeypatch):
    warped(monkeypatch, lambda real, p0, mouth, h, u: real(p0, (mouth[0] - 0.5, mouth[1]), h, u))
    root, ep, bible = project(tmp_path, "yetiskin_saga")
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: pytest.fail("ıska atış çizime girdi"))
    m = render_worker.run(str(ep), bible, 0, 6, str(root))
    assert m["status"] == "BLOCKED" and m["error"] == "AKSIYON_OKUNAMIYOR", m
    assert any(p.startswith("[object_motion]") for p in m["problems"]), m["problems"]
