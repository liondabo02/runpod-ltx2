"""Genel poz sıçraması (H5): oyuncunun omuz/dirsek/el/baş/ayak noktaları tek karede ışınlanamaz. Durum değişimleri (tepki, replik başı/sonu,
yürüyüş sonu, taşıma, eylem türü, vuruş sınırı) geçişli olmalı; ölçü çizime giden pozdan, render kapısı POZ_SICRAMASI. Tamamen sentetik projeler."""
import json
import math

import pytest

import test_throw_entry as te          # sys.path ayarı da buradan
import pose_blend
import puppet2d as pp
import readability as rd
import render2d as r2
import render_worker
import shot_motion as sm
import shot_planner as sp

IDS = ("a", "b")


def build(root, kind="idle", react=None, line=False, hold=None, next_kind="idle", heights=(1.0, 1.75)):
    ep = root / "episodes" / "e1"; ep.mkdir(parents=True); (root / "assets").mkdir()
    bible = {"id": "pj", "characters": [{"id": c, "name": c, "age": 6 if h < 1.3 else 40} for c, h in zip(IDS, heights)]}
    for c, h in zip(IDS, heights):
        (root / "assets" / f"{c}.spec.json").write_text(json.dumps({"height_m": h}))
    (root / "locations.json").write_text(json.dumps({"y": {"pieces": []}}))
    (root / "series-bible.json").write_text(json.dumps(bible))
    moving = kind in ("walk", "run", "carry")

    def beat(i, k, x0, x1, react_):
        b = {"t_start": 6 * i, "t_end": 6 * i + 6, "scene_id": "S1", "shot_id": f"p{i}", "location": "y", "characters": list(IDS), "action": "", "camera": "orta",
             "choreo": {"motion": {"a": dict({"kind": k, "x0": x0}, **({"x1": x1} if k in ("walk", "run", "carry") else {})), "b": {"kind": "idle", "x0": 1.2}}}}
        if react_:
            b["choreo"]["react"] = {"a": {"t": 2.5, "kind": react_}}
        if hold:
            b["choreo"]["objects"] = [{"prop": hold, "track": [{"t": 0, "holder": "a"}, {"t": 6, "holder": "a"}]}]
        return b
    beats = [beat(0, kind, -1.6, 0.0, react), beat(1, next_kind, 0.0 if moving else -1.6, None, None)]
    (ep / "beat_sheet.json").write_text(json.dumps({"beats": beats}))
    plan = sp.plan(str(ep), bible, str(root / "assets"), 0, 12)
    if line:
        for i, b in enumerate(plan["beats"]):
            b["lines"] = [{"char": "a", "text": "bir iki üç", "start": 6 * i + 1.3, "end": 6 * i + 3.9, "cues": [], "mood": "neutral"}]
    return plan, pp.designs_for(bible, str(root / "assets")), root, ep, bible


# her satır eski motorda en az bir ışınlanma üreten bir durum değişimini taşır
SCENES = {
    "yuruyus_ortasinda_sasirma_tasirken": dict(kind="walk", react="surprise", hold="bottle"),
    "bos_elle_sasirma": dict(kind="idle", react="surprise"),
    "konusma_vurgusu_ve_replik_sinirlari": dict(kind="idle", line=True, next_kind="wave"),
    "tasiyip_durma_ve_gulme": dict(kind="carry", react="laugh", line=True, hold="bottle", next_kind="look"),
    "konusurken_tas_tasima_ve_uzanma": dict(kind="walk", line=True, hold="stone", next_kind="reach"),
    "ziplama": dict(kind="jump"),
    "dans_sonra_el_sallama": dict(kind="dance", line=True, next_kind="wave"),
    "oturma_ve_sasirma": dict(kind="sit", react="surprise", hold="bottle"),
    "iki_yetiskin": dict(kind="walk", react="surprise", line=True, heights=(1.9, 1.7)),
    "iki_cocuk": dict(kind="idle", react="surprise", line=True, hold="bottle", heights=(0.98, 1.1)),
}


def blocking(plan, des):
    return rd.pose_jump_problems(rd.pose_jumps(plan, des))


@pytest.mark.parametrize("name", sorted(SCENES))
def test_no_actor_pose_teleports_across_state_changes(tmp_path, name):
    plan, des = build(tmp_path, **SCENES[name])[:2]
    bad = blocking(plan, des)
    assert not bad, bad[:6]


@pytest.mark.parametrize("name", sorted(te.CONFIGS))
def test_throw_scenes_have_no_pose_teleport(tmp_path, name):
    plan, des = te.planned(tmp_path, name)[:2]
    bad = blocking(plan, des)
    assert not bad, bad[:6]


# ---------------------------------------------------------------- ön <-> profil dönüşü (C2a)
TURNS = {
    "kosu": dict(kind="run"),
    "kosarken_sasirma": dict(kind="run", react="surprise"),
    "kosarken_gulme_tasirken": dict(kind="run", react="laugh", hold="bottle"),
    "kosu_iki_yetiskin": dict(kind="run", heights=(1.9, 1.7)),
    "kosu_iki_cocuk_replikli": dict(kind="run", line=True, heights=(0.98, 1.1)),
    "kosu_sonra_el_sallama": dict(kind="run", next_kind="wave", react="surprise"),
}


def views_over(plan, des, a, b, fps=96):
    out = []
    for k in range(int((b - a) * fps)):
        pose = next(i for i in r2.poses_at(plan, des, a + k / fps) if i[0] == "a")[2]
        out.append((a + k / fps, pp.view_of(pose), pose))
    return out


@pytest.mark.parametrize("name", sorted(TURNS))
def test_front_profile_turn_has_no_single_frame_arm_jump(tmp_path, name):
    plan, des = build(tmp_path, **TURNS[name])[:2]
    seq = views_over(plan, des, 0.0, 11.9, fps=24)
    assert any(v == "side" for _t, v, _p in seq) and any(v != "side" for _t, v, _p in seq), "sahne dönüş içermiyor"
    rows = rd.pose_jumps(plan, des)
    assert not rows, rows[:6]                       # 'view' türü dahil hiç satır yok


@pytest.mark.parametrize("name", sorted(TURNS) + sorted(SCENES))
def test_cheap_side_check_agrees_with_the_full_base_pose(tmp_path, name):
    plan, des = build(tmp_path, **{**SCENES, **TURNS}[name])[:2]
    for k in range(int(11.9 * 24)):
        t = k / 24
        beat = next(b for b in plan["beats"] if b["t_start"] <= t < b["t_end"])
        for cid in beat["cast"]:
            full = r2._base_pose(plan, des, beat, cid, t, r2._positions(beat, des, t - beat["t_start"]))[0]
            assert r2.side_view_at(plan, des, beat, cid, t) == (pp.view_of(full) == "side"), (cid, t)


def test_turn_starts_at_the_old_drawing_and_ends_at_the_new_one(tmp_path):
    """Dönüşün başında kol eklemleri önceki görünüşün geometrisinde, TURN_S sonra yeni görünüşün kendi geometrisinde."""
    plan, des = build(tmp_path, kind="run")[:2]
    seq = views_over(plan, des, 0.0, 1.0, fps=960)
    i = next(i for i in range(1, len(seq)) if (seq[i][1] == "side") != (seq[i - 1][1] == "side"))
    before, after = seq[i - 1][2], seq[i][2]
    assert pp.turning(after) and after["side_mix"] < 0.02
    for side in "LR":
        gap = max(math.dist(a, b) for a, b in zip(pp.arm_joints(des["a"], before, side), pp.arm_joints(des["a"], after, side)))
        assert gap < 0.03 * des["a"]["height"], (side, gap)
    later = views_over(plan, des, seq[i][0] + pose_blend.TURN_S + 0.01, seq[i][0] + pose_blend.TURN_S + 0.05)[0][2]
    assert later["view"] == "side" and not pp.turning(later)


@pytest.mark.parametrize("view,mix", [("side", 0.0), ("side", 0.5), ("front", 0.5), ("front", 1.0)])
def test_drawn_hand_is_where_the_measure_says_during_a_turn(view, mix):
    """Çizim ile ölçü aynı geometri: dönüş pozunda el pikseli hand_offset'in gösterdiği yerdedir (iki rig de)."""
    des = pp.derive_design({"id": "q", "age": 30}, {"height_m": 1.75})
    des["skin"] = (1, 254, 3)                       # sahnede başka yerde olmayan renk
    pose = sm.base_pose(0.0)
    pose.update({"view": view, "yaw": 0.8, "side_mix": mix, "aL": [-0.4, 1.5], "aR": [0.2, -1.5]})
    cv = pp.Cv(1280, 720, 1)
    ppm = 250.0
    pp.draw_character(cv, des, pose, {"hide": ()}, 640.0, 660.0, ppm)
    img = cv.done().convert("RGB")
    for side in "LR":
        dx, h = pp.hand_offset(des, pose, side)
        x, y = int(round(640 + dx * ppm)), int(round(660 - h * ppm))
        near = [img.getpixel((x + i, y + j)) for i in range(-9, 10) for j in range(-9, 10)]
        assert any(g > 150 and r < 80 and b < 80 for r, g, b in near), (side, view, mix, x, y)


def test_snapping_the_turn_is_caught_and_blocks(tmp_path, monkeypatch):
    """Bilerek bozma: eski davranış (görünüş tek karede, geçişsiz) 'view' satırı üretir ve kapı bunu durdurur."""
    monkeypatch.setattr(pose_blend, "side_weight", lambda side_at, t, window=0.25, depth=0: 1.0 if side_at(t) else 0.0)
    rows = rd.pose_jumps(*build(tmp_path, kind="run")[:2])
    assert any(r["kind"] == "view" for r in rows), rows
    assert any("profil" in b["why"] for b in rd.pose_jump_problems(rows))


def test_render_stops_before_drawing_when_a_turn_snaps(tmp_path, monkeypatch):
    _p, _d, root, ep, bible = build(tmp_path, kind="run")
    monkeypatch.setattr(pose_blend, "side_weight", lambda side_at, t, window=0.25, depth=0: 1.0 if side_at(t) else 0.0)
    drawn = []
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: drawn.append(1))
    m = render_worker.run(str(ep), bible, 0, 12, str(root))
    assert m["status"] == "BLOCKED" and m["error"] == "POZ_SICRAMASI", m
    assert not drawn


def test_surprise_still_reaches_its_full_pose_after_the_transition(tmp_path):
    plan, des = build(tmp_path, kind="idle", react="surprise")[:2]
    arm = max(abs(next(i for i in r2.poses_at(plan, des, 2.5 + k / 48) if i[0] == "a")[2]["aR"][1]) for k in range(48))
    assert arm > 1.7, arm


def test_same_pose_when_frames_are_asked_in_any_order(tmp_path):
    """Parça parça / çok işçili üretim: poz geçmişten hesaplanır, çağrı sırasına bağlı durum tutulmaz."""
    plan, des = build(tmp_path, **SCENES["tasiyip_durma_ve_gulme"])[:2]
    times = [2.55, 5.97, 6.03, 6.1, 1.31]
    first = {t: [i[2] for i in r2.poses_at(plan, des, t)] for t in times}
    for t in reversed(times):
        assert [i[2] for i in r2.poses_at(plan, des, t)] == first[t]


def test_no_transition_across_a_location_change(tmp_path):
    plan, des = build(tmp_path, kind="idle", next_kind="wave")[:2]
    plan["beats"][1]["loc"] = "baska_yer"
    assert r2._history(plan, "a", plan["beats"][1], 5.9) is None
    assert r2.pose_signature(plan, des, plan["beats"][1], "a", 5.9) is None


# ---------------------------------------------------------------- bilerek eklenen hatalar
def test_removing_the_pose_transition_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(pose_blend, "apply", lambda raw_at, state_at, t, height, depth=0: raw_at(t))
    bad = blocking(*build(tmp_path, **SCENES["yuruyus_ortasinda_sasirma_tasirken"])[:2])
    assert any("ışınlanma" in b["why"] and "a:" in b["why"] for b in bad), bad


def test_too_short_transition_is_caught_as_too_fast(tmp_path, monkeypatch):
    monkeypatch.setattr(pose_blend, "TRANSITION_S", 0.05)
    bad = blocking(*build(tmp_path, **SCENES["bos_elle_sasirma"])[:2])
    assert bad, "çok kısa geçiş yakalanmalıydı"


def test_speech_accent_snapping_on_is_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "ACCENT_BLEND", 1e-6)
    bad = blocking(*build(tmp_path, **SCENES["konusma_vurgusu_ve_replik_sinirlari"])[:2])
    assert bad


def test_elbow_snapping_to_bent_is_caught(tmp_path, monkeypatch):
    """Eski davranış: yönlü uzanma başlar başlamaz (ağırlığı sıfırken bile) dirsek tam bükülü."""
    monkeypatch.setattr(pp, "bend_weight", lambda pose, side: 1.0 if ("d" + side) in pose else 0.0)
    found = []
    for i, name in enumerate(sorted(te.CONFIGS)):
        found += blocking(*te.planned(tmp_path / str(i), name)[:2])
    assert any("dirsek" in b["why"] for b in found), found


def test_render_stops_before_drawing_when_a_pose_teleports(tmp_path, monkeypatch):
    _p, _d, root, ep, bible = build(tmp_path, kind="idle", react="surprise")
    monkeypatch.setattr(pose_blend, "apply", lambda raw_at, state_at, t, height, depth=0: raw_at(t))
    drawn = []
    monkeypatch.setattr(r2, "render_window", lambda *a, **k: drawn.append(1))
    m = render_worker.run(str(ep), bible, 0, 12, str(root))
    assert m["status"] == "BLOCKED" and m["error"] == "POZ_SICRAMASI", m
    assert not drawn and (ep / "render" / "pose_jumps.json").exists()
    assert render_worker.exit_code(m) != 0
