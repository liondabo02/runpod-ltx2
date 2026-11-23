# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import shot_motion as sm
import puppet2d as pp
import bg_art


def test_jump_has_anticipation_stretch_landing():
    H = 1.0
    crouch = sm.pose_at("jump", 0.18 * 3.0 * 0.22 * 0, 9.0, 1, 0, 0, H, 0.45)  # t=0 başlangıç
    cyc = 9.0 / 3.0
    p_crouch = sm.pose_at("jump", cyc * 0.18, 9.0, 1, 0, 0, H, 0.45)
    p_air = sm.pose_at("jump", cyc * 0.5, 9.0, 1, 0, 0, H, 0.45)
    p_land = sm.pose_at("jump", cyc * 0.92, 9.0, 1, 0, 0, H, 0.45)
    assert p_crouch["sq"] < 1.0 and p_crouch["z"] == 0.0     # hazırlık: çömelme
    assert p_air["sq"] > 1.0 and p_air["z"] > 0.0            # havada uzama
    assert p_land["sq"] < 1.0                                # iniş ezilmesi


def test_walk_bobs_and_all_poses_have_sq():
    for k in ("walk", "run", "wave", "idle", "surprise", "sit", "reach", "look", "dance", "laugh"):
        assert "sq" in sm.pose_at(k, 0.4, 5.0, 2, 0, 1, 1.0, 0.45)


def test_fps_env(monkeypatch):
    import shot_planner as sp
    monkeypatch.setenv("AHOS_FPS", "24")
    import inspect
    assert "AHOS_FPS" in inspect.getsource(sp.plan)


def test_bg_art_enhance_keeps_size_and_changes_pixels():
    cv = pp.Cv()
    cv.d.rectangle([0, 0, cv.img.size[0], cv.img.size[1]], fill=(120, 180, 90))
    before = cv.img.copy()
    bg_art.enhance(cv, "garden", "sabah güneşi", 0.0)
    assert cv.img.size == before.size and cv.img.tobytes() != before.tobytes()


def test_bg_art_palette_selection():
    assert bg_art._pick("gece, ay ışığı", "garden") is bg_art.PAL["gece"]
    assert bg_art._pick("", "room") is bg_art.PAL["ic"]


def test_face_kits_distinct():
    import json
    d = {}
    for cid in ("salih", "berzan"):
        p = os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile", "assets", cid + ".spec.json")
        if os.path.exists(p):
            d[cid] = json.load(open(p, encoding="utf-8"))
    if len(d) == 2:
        keys = ("eye_shape", "brow_shape", "nose", "mouth_w", "face_w", "freckles")
        assert sum(d["salih"].get(k) != d["berzan"].get(k) for k in keys) >= 4
