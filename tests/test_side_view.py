import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import numpy as np
import puppet2d as pp, shot_motion as sm, turn_sheet as T
from PIL import ImageChops, ImageOps
BIBLE = os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile", "series-bible.json")
DES = T.design_set(BIBLE)

def _img(des, yaw, pose=None):
    cv = pp.Cv(320, 400); p = pose or sm.base_pose(0.0); p["yaw"] = yaw
    pp.draw_character(cv, des, p, {"mouth": "B"}, 160, 380, 200, 0.3)
    return cv.img.convert("RGB")

def _bbox(im):
    a = np.asarray(im).astype(int); m = (a.sum(axis=2) < 740)
    ys, xs = np.where(m); return xs.min(), ys.min(), xs.max(), ys.max()

def test_view_classification_and_thresholds():
    assert pp.view_of({"yaw": 0.0}) == "front" and pp.view_of({"yaw": 0.6}) == "three_quarter" and pp.view_of({"yaw": 0.9}) == "side"
    assert pp.view_of({"yaw": -1.0}) == "side"

def test_every_character_draws_in_all_views_with_stable_height():
    for cid, d in DES.items():
        hf = None
        for yaw in (0.0, 0.6, 1.0, -1.0):
            im = _img(d, yaw); x0, y0, x1, y1 = _bbox(im)
            h = y1 - y0
            if yaw == 0.0: hf = h
            assert abs(h - hf) / hf < 0.14, (cid, yaw, h, hf)            # boy yan görünüşte korunur (kimlik/oran)
            assert x1 - x0 > 20

def test_facing_direction_follows_yaw_sign():
    # burun/yüz yönü: kafa bölgesinde açık ten renginin ağırlık merkezi bakılan tarafa kayar (aynı karakterin sağ/sol görüntüsü ayna olmalı)
    for cid in ("aden", "esra", "harun"):
        r = _img(DES[cid], 1.0); l = _img(DES[cid], -1.0)
        diff = np.asarray(ImageChops.difference(ImageOps.mirror(l), r)).astype(int).sum(axis=2)
        assert (diff > 60).mean() < 0.02, (cid, (diff > 60).mean())       # sol bakış = sağ bakışın aynası (durağan poz)

def test_side_walk_feet_use_world_positions_no_slide():
    import foot_slide as F
    SM = F._load(os.path.join(os.path.dirname(__file__), "..", "tools", "shot_motion.py"), "sm_side")
    for H in (1.0, 1.7):
        assert F.check(SM, "walk", H)["pass"]
    # ayak dünya konumu profilde de aynı alandan (fL/fR) çizilir
    d = DES["harun"]; p = sm.pose_at("walk", 1.0, 3.0, 0, -1, 1, d["height"], 0.5 * d["height"]); p["yaw"] = 1.0; p["view"] = "side"
    assert "fL" in p and pp.view_of(p) == "side"
    _img(d, 1.0, p)

def test_all_accessories_and_hair_styles_render_in_profile():
    base = dict(DES["aden"])
    for style in ("short", "bob", "ponytail", "spiky", "bun", "bald", "wavy_long", "curly", "hijab"):
        for acc in ("none", "star", "glasses", "hat", "beanie", "bow", "flower_pin"):
            d = dict(base, hair_style=style, accessory=acc, scarf=(200, 60, 90)); _img(d, 1.0)
    h = dict(base, species="hedgehog"); _img(h, -1.0)

def test_run_uses_profile_and_walk_uses_three_quarter():
    d = DES["harun"]; H = d["height"]
    r = sm.pose_at("run", 1.2, 3.0, 0, -1, 1, H, 0.5 * H); w = sm.pose_at("walk", 1.2, 3.0, 0, -1, 1, H, 0.5 * H)
    assert pp.view_of(r) == "side" and pp.view_of(w) == "three_quarter"

def test_view_does_not_flicker_during_a_stride():
    d = DES["harun"]; H = d["height"]
    for kind in ("walk", "run"):
        seq = [pp.view_of(sm.pose_at(kind, i / 24, 3.0, 0, -1, 1, H, 0.5 * H)) for i in range(72)]
        changes = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
        assert changes <= 4, (kind, changes, seq)             # başlangıçta/bitişte geçiş var, adım başına titreme yok

def test_side_rig_is_part_of_cache_stamp():
    import render2d as r2
    assert "puppet_side.py" in r2.ENGINE_FILES              # profil rig değişince eski kareler kullanılmaz
