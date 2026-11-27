"""Ayak tozu: yalnız ayak gerçekten ilerlerken, varışta biter, hedefi örtmez. Ölçü çizilen karelerden. Yalnız sentetik projeler."""
import json, os, sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import fx_layer  # noqa: E402
import motion_continuity as mc  # noqa: E402
import puppet2d as pp  # noqa: E402
import setpieces2d  # noqa: E402
import shot_motion as sm  # noqa: E402
import shot_planner as sp  # noqa: E402

FPS = 12
# (kimlik, yaş, boy, tür, başlangıç, varış, kutuların x'i)
CONFIGS = {
    "buyuk_yaklasma_saga": ("baba", 40, 1.9, "approach", -1.8, 1.4, -0.5),
    "kucuk_kosu_sola": ("nil", 6, 0.98, "run", 1.7, -1.5, -0.4),
    "buyuk_yuruyus_sola": ("dede", 60, 1.75, "walk", 1.8, -1.6, -0.8),
}


@pytest.fixture(autouse=True)
def _default_style(monkeypatch):
    monkeypatch.delenv("AHOS_STYLE", raising=False)
    monkeypatch.delenv("AHOS_SERIES_DIR", raising=False)


def planned(tmp_path, name):
    cid, age, h, kind, x0, x1, bins_x = CONFIGS[name]
    root = tmp_path / name; ep = root / "episodes" / "e1"; (root / "assets").mkdir(parents=True); ep.mkdir(parents=True)
    bible = {"id": name, "characters": [{"id": cid, "name": cid, "age": age}]}
    json.dump({"height_m": h}, open(root / "assets" / f"{cid}.spec.json", "w"))
    json.dump({"yer": {"pieces": [["bins", bins_x]]}}, open(root / "locations.json", "w"))
    json.dump(bible, open(root / "series-bible.json", "w"))
    base = {"scene_id": "S1", "location": "yer", "characters": [cid], "action": "", "camera": "orta"}
    if kind == "approach":      # önceki plan x0'da biter; yeni plan işareti x1: karakter yürüyerek varır, plan sürerken DURUR (eski hata)
        beats = [dict(base, t_start=0, t_end=2, shot_id="p0", choreo={"motion": {cid: {"kind": "idle", "x0": x0}}}),
                 dict(base, t_start=2, t_end=9, shot_id="p1", choreo={"motion": {cid: {"kind": "idle", "x0": x1}}})]
        span = (2.0, 7.0)
    else:
        beats = [dict(base, t_start=0, t_end=5, shot_id="p1", choreo={"motion": {cid: {"kind": kind, "x0": x0, "x1": x1}}})]
        span = (0.0, 5.0)
    json.dump({"beats": beats}, open(ep / "beat_sheet.json", "w"))
    plan = sp.plan(str(ep), bible, str(root / "assets"), 0, beats[-1]["t_end"])
    des = pp.designs_for(bible, str(root / "assets"))
    times = [span[0] + i / FPS for i in range(int((span[1] - span[0]) * FPS))]
    return plan, des, cid, h, times


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_drawn_dust_only_while_advancing_and_never_over_set_pieces(tmp_path, name):
    plan, des, cid, _h, times = planned(tmp_path, name)
    m, why = mc.dust_report(mc.sample_dust(plan, des, cid, times))
    assert not why, (why, m)
    assert m["dusty_frames"] >= 3, m                          # toz tümden kaybolmadı (boş yere geçen test değil)


def test_approach_really_stops_inside_the_beat(tmp_path):
    plan, des, cid, h, _t = planned(tmp_path, "buyuk_yaklasma_saga")
    b = plan["beats"][1]; ws = b["motion"][cid]["approach"]["walk_s"]
    assert ws < 0.6 * (b["t_end"] - b["t_start"])
    assert fx_layer.dust_plan(b["motion"][cid], ws + 0.05, 7.0, h)["puffs"] == []


def test_puffs_are_born_where_a_foot_landed_and_stay_put():
    H, dur, m = 1.9, 5.0, {"kind": "walk", "x0": -1.8, "x1": 1.8, "seed": 0}
    tracks = {}
    for i in range(int(dur * 48)):
        for x, _y, r, age in fx_layer.dust_plan(m, i / 48, dur, H)["puffs"]:
            born = round(i / 48 - age * fx_layer.DUST_LIFE["walk"], 3)
            tracks.setdefault(born, []).append((x, r))
    assert len(tracks) >= 3
    for born, pts in tracks.items():
        assert max(x for x, _ in pts) - min(x for x, _ in pts) <= 0.11 * H          # gövdeyle sürüklenmez (gövde aynı sürede çok daha fazla yol alır)
        poses = [sm.pose_at("walk", born + d, dur, 0, -1.8, 1.8, H, H * 0.45) for d in (-0.03, 0.02)]
        assert any(poses[0]["h" + s] > 0 and poses[1]["h" + s] == 0 for s in "LR"), born


def test_standing_idle_and_zero_length_walk_make_no_dust():
    for m in ({"kind": "idle", "x0": 0, "x1": 0}, {"kind": "walk", "x0": 0.4, "x1": 0.4}, {"kind": "carry", "x0": -1, "x1": 1}):
        assert all(not fx_layer.dust_plan(m, i / 24, 4.0, 1.5)["puffs"] for i in range(96))


# ---------------------------------------------------------------- bilerek eklenen hatalar
def test_clock_driven_dust_after_arrival_is_caught(tmp_path, monkeypatch):
    """Eski davranış: plan süresinin %85'ine kadar, varıştan bağımsız toz."""
    plan, des, cid, h, times = planned(tmp_path, "buyuk_yaklasma_saga")

    def old_like(m, lt, dur, H):
        x = sm.motion_x(m, lt, dur, H)
        puffs = [(x - 0.9 * H, 0.1, 0.1 * H, 0.5)] if lt / dur < 0.85 else []
        return {"puffs": puffs, "gate": 1.0, "dir": 1.0, "run": False, "travelled": 9.0, "x": x}
    monkeypatch.setattr(fx_layer, "dust_plan", old_like)
    _m, why = mc.dust_report(mc.sample_dust(plan, des, cid, times))
    assert any("dururken toz" in w for w in why), why
    assert any("hiç yürünmeyen" in w for w in why), why


def test_dust_drawn_over_set_pieces_is_caught(tmp_path, monkeypatch):
    plan, des, cid, _h, times = planned(tmp_path, "kucuk_kosu_sola")
    real_dust, real_pieces, calls = fx_layer.dust, setpieces2d.draw, []

    def spy(*a):
        calls.append(a); real_dust(*a)

    def pieces_then_dust(cv, cam, loc, t=0.0, pieces=None):
        real_pieces(cv, cam, loc, t, pieces=pieces)
        while calls:
            real_dust(*calls.pop())
    monkeypatch.setattr(fx_layer, "dust", spy)
    monkeypatch.setattr(setpieces2d, "draw", pieces_then_dust)
    rows = mc.sample_dust(plan, des, cid, times)
    _m, why = mc.dust_report(rows)
    assert any("örtüyor" in w for w in why), (why, _m)
