"""C3i: elde nesneyle bir önceki vuruştan kesintisiz gelen oyuncunun tutan eli vuruş sınırında değişmez; tercih edilen el farklıysa nesne
görünür biçimde el değiştirir. Ölçü dünya koordinatında nesne sıçraması (object_jumps), render kapısı NESNE_SICRAMASI. Tamamen sentetik projeler."""
import json

import pytest

import test_throw_entry as te          # sys.path ayarı
import puppet2d as pp
import readability as rd
import render2d as r2
import render_worker
import shot_planner as sp

# (tutan, öbürü, tutan boyu, öbür boyu, ilk vuruşta yürüyüş x0->x1, kap x, öbürünün x'i)
CONFIGS = {
    "yetiskin_sola_yuruyup_saga_atar": ("dede", "torun", 1.85, 1.0, (1.2, 0.2), 1.6, -1.4),
    "cocuk_saga_yuruyup_sola_atar": ("zip", "robo", 1.0, 1.6, (-1.0, 0.2), -1.5, 1.6),
}


def build(root, name, second_loc=None, transition=None):
    holder, other, h1, h2, (x0, x1), bin_x, ox = CONFIGS[name]
    ep = root / "episodes" / "e1"; ep.mkdir(parents=True); (root / "assets").mkdir()
    bible = {"id": name, "characters": [{"id": c, "name": c, "age": 6 if h < 1.3 else 40} for c, h in ((holder, h1), (other, h2))]}
    for c, h in ((holder, h1), (other, h2)):
        (root / "assets" / f"{c}.spec.json").write_text(json.dumps({"height_m": h}))
    (root / "locations.json").write_text(json.dumps({"yer": {"pieces": [["bins", bin_x]]}, "yer2": {"pieces": [["bins", bin_x]]}}))
    (root / "series-bible.json").write_text(json.dumps(bible))
    b0 = {"t_start": 0, "t_end": 4, "scene_id": "S1", "shot_id": "p0", "location": "yer", "characters": [holder, other], "action": "", "camera": "genel",
          "choreo": {"motion": {holder: {"kind": "carry", "x0": x0, "x1": x1}, other: {"kind": "idle", "x0": ox}},
                     "objects": [{"prop": "bottle", "track": [{"t": 0, "holder": holder}, {"t": 4, "holder": holder}]}]}}
    b1 = {"t_start": 4, "t_end": 9, "scene_id": "S1", "shot_id": "p1", "location": second_loc or "yer", "characters": [holder, other], "action": "", "camera": "genel",
          "choreo": {"motion": {holder: {"kind": "idle", "x0": x1}, other: {"kind": "idle", "x0": ox}},
                     "objects": [{"prop": "bottle", "track": [{"t": 0, "holder": holder}, {"t": 2.2, "holder": holder}, {"t": 3.4, "at": "bin_green", "hide": True}]}]}}
    if transition:
        b1["transition"] = transition
    (ep / "beat_sheet.json").write_text(json.dumps({"beats": [b0, b1]}))
    plan = sp.plan(str(ep), bible, str(root / "assets"), 0, 9)
    return plan, pp.designs_for(bible, str(root / "assets")), root, ep, bible, holder


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_held_object_keeps_its_hand_across_the_beat_and_swaps_visibly(tmp_path, name):
    plan, des, *_r, holder = build(tmp_path, name)
    b0, b1 = plan["beats"]
    assert r2.carry_info(b0, holder, 3.999)["hand"] != r2.pick_hand(b1, holder), "kurulum: vuruşlar farklı el istemeli"
    assert b1["hand_in"] == {holder: r2.carry_info(b0, holder, 3.999)["hand"]}
    assert r2.hand_at(b1, holder, 0.0) == b1["hand_in"][holder]
    sw = r2.hand_swap(b1, holder)
    assert sw and sw[3] <= 2.2 - 0.45 - r2.SWAP_BEFORE_ACT_S + 1e-6 and sw[3] - sw[2] >= r2.SWAP_MIN_S - 1e-6
    assert r2.hand_at(b1, holder, sw[3]) == r2.pick_hand(b1, holder)
    assert not rd.object_jumps(plan, des)
    assert not rd.pose_jump_problems(rd.pose_jumps(plan, des))


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_both_hands_are_on_the_object_mid_swap(tmp_path, name):
    plan, des, *_r, holder = build(tmp_path, name)
    b1 = plan["beats"][1]; _o, _n, a, b = r2.hand_swap(b1, holder)
    t = b1["t_start"] + (a + b) / 2
    items = {i[0]: i for i in r2.poses_at(plan, des, t)}
    _c, d, p, *_x = items[holder]
    (x, y, *_s), = r2.objects_at(plan, des, t).values()
    grip = r2.object_state.grip_of("bottle")
    for side in "LR":
        hx, hh = pp.hand_offset(d, p, side)
        assert abs(p["x"] + hx - x) < 0.6 * pp.HAND_R_K * d["height"] + 0.03 and abs(hh - grip - y) < 3 * pp.HAND_R_K * d["height"], side


def test_no_hand_carry_across_a_location_change(tmp_path):
    plan, *_r, holder = build(tmp_path, "yetiskin_sola_yuruyup_saga_atar", second_loc="yer2")
    assert plan["beats"][1]["hand_in"] == {}


def test_hand_continuity_is_the_same_when_rendering_only_the_second_beat(tmp_path):
    """Parça parça üretim: pencere öncesi vuruş da planlayıcıda bağlanır."""
    full, des, root, ep, bible, holder = build(tmp_path, "cocuk_saga_yuruyup_sola_atar")
    part = sp.plan(str(ep), bible, str(root / "assets"), 4, 9)
    assert part["beats"][0]["hand_in"] == full["beats"][1]["hand_in"]


# ---------------------------------------------------------------- bilerek eklenen hatalar
def test_hand_switch_at_the_beat_boundary_is_caught(tmp_path, monkeypatch):
    """Eski davranış: el vuruş başına seçilir, nesne sınırda öbür ele ışınlanır."""
    monkeypatch.setattr(r2, "hand_link", lambda prev, beat: beat.__setitem__("hand_in", {}) or {})
    plan, des, *_r, holder = build(tmp_path, "yetiskin_sola_yuruyup_saga_atar")
    bad = rd.object_jumps(plan, des)
    assert any(r["kind"] == "teleport" and r["t"] == pytest.approx(4.0, abs=0.02) and r["hands"][0] != r["hands"][1] for r in bad), bad


def test_instant_swap_inside_the_beat_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(r2, "swap_weight", lambda beat, cid, lt: None)
    plan, des, *_r = build(tmp_path, "cocuk_saga_yuruyup_sola_atar")
    assert rd.object_jumps(plan, des)


def test_render_stops_before_drawing_when_an_object_teleports(tmp_path, monkeypatch):
    monkeypatch.setattr(r2, "hand_link", lambda prev, beat: beat.__setitem__("hand_in", {}) or {})
    _p, _d, root, ep, bible, _h = build(tmp_path, "yetiskin_sola_yuruyup_saga_atar")
    drawn = []
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: drawn.append(1))
    m = render_worker.run(str(ep), bible, 0, 9, str(root))
    assert m["status"] == "BLOCKED" and m["error"] == "NESNE_SICRAMASI", m
    assert not drawn and (ep / "render" / "object_jumps.json").exists()
