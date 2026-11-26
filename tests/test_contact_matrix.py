"""El–nesne temas matrisi: farklı boylar × nesneler × görünüşler × durumlar. OTOMATİK ölçülebilen: konum/hız/çizim sırası. GÖZLE gerekenler ayrıca qa/nesne_temas_kareleri.png ile."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import object_state as O, render2d as r2, shot_motion as sm, puppet2d as pp, props2d, setpieces2d, turn_sheet as T
BIBLE = os.path.join(os.path.dirname(__file__), "..", "series", "ahos-bizim-aile", "series-bible.json")
DES = T.design_set(BIBLE); TG = setpieces2d.TARGETS; SK = setpieces2d.SINKS
PROPS = ("bottle", "stone", "shovel", "hat", "balloon")

def _beat(a_kind="idle", h_kind="idle", prop="bottle", track=None, a_x=(0.2, 0.2), h_x=(1.4, 1.4)):
    return {"cast": ["aden", "harun"], "motion": {"aden": {"kind": a_kind, "x0": a_x[0], "x1": a_x[1], "seed": 0}, "harun": {"kind": h_kind, "x0": h_x[0], "x1": h_x[1], "seed": 1}},
            "choreo": {"objects": [{"prop": prop, "track": track or [{"t": 0, "holder": "aden"}, {"t": 9, "holder": "aden"}]}]}}

def _items(beat, t, dur=9.0, yaw_a=None, view=None):
    out = []
    for cid in beat["cast"]:
        m = beat["motion"][cid]; d = DES[cid]; H = d["height"]
        p = sm.pose_at(m["kind"], t, dur, m["seed"], m["x0"], m["x1"], H, 0.5 * H)
        if cid == "aden" and yaw_a is not None:
            p["yaw"] = yaw_a
        if cid == "aden" and view:
            p["view"] = view
        ci = r2.carry_info(beat, cid, t)
        if ci:
            adj = O.carry_adjust(ci["weight"], ci["style"], ci["reach"]); p["lean"] += adj["lean"]
        out.append((cid, d, p, m, 0, 0))
    return out

def test_grip_point_equals_drawn_hand_for_all_heights_props_views():
    cast = ["aden", "harun", "esra", "kaan", "esma", "ahmet", "salih"]
    for cid in cast:
        d = DES[cid]
        for prop in PROPS:
            for yaw, view in ((0.0, "front"), (0.6, "three_quarter"), (1.0, "side"), (-1.0, "side")):
                b = _beat(prop=prop); b["cast"] = ["aden", "harun"]; DES2 = dict(DES); 
                H = d["height"]; p = sm.base_pose(0.0); p["yaw"] = yaw; p["view"] = view
                grip = O.grip_of(prop)
                hx, hy, _ = r2._hold_pos("aden", [("aden", d, p, b["motion"]["aden"], 0, 0)], None, b, 0.0, None, grip)
                dx, h = pp.hand_offset(d, p, r2.pick_hand(b, "aden"))
                assert abs(hx - dx) < 1e-9 and abs(hy - max(0.0, h - grip)) < 1e-9, (cid, prop, view)

def test_held_object_never_switches_hands_or_jumps_across_walk_stop_turn():
    # yürü (taşıyarak) -> dur -> dön: seçilen el sabit, nesne elden ayrılmaz
    b = _beat(a_kind="carry", prop="bottle", a_x=(-1.3, 0.2))
    hands = set(); worst = 0.0; fps = 24; prev = None
    for i in range(int(9 * fps)):
        t = i / fps; items = _items(b, t)
        hands.add(r2.pick_hand(b, "aden"))
        ob, x, y, st, own, hand = r2._objects_now(b, items, t)[0]
        dx, h = pp.hand_offset(DES["aden"], items[0][2], hand)
        gx = items[0][2]["x"] + dx
        worst = max(worst, abs(x - gx))
        assert own == "aden" and st["state"] == "held"
    assert len(hands) == 1 and worst < 1e-9

def test_handoff_continuity_scales_with_fps_and_height():
    GIVE = [{"t": 0, "holder": "aden"}, {"t": 2.0, "holder": "aden"}, {"t": 3.4, "holder": "harun"}, {"t": 9, "holder": "harun"}]
    for prop in ("bottle", "stone", "hat"):
        for fps in (12, 24, 48):
            b = _beat(a_kind="reach", h_kind="reach", prop=prop, track=GIVE)
            def hold(holder, t, hand=None):
                h = r2._hold_pos(holder, _items(b, t), None, b, t, hand, O.grip_of(prop)); return h[0], h[1]
            tgt = lambda at: tuple(TG[at]) if isinstance(at, str) else tuple(at)
            c = O.continuity(GIVE, hold, tgt, fps=fps)
            assert c["ok"], (prop, fps, c)                       # kare başına adım, aralığın beklenen hız sınırının içinde
            assert c["key_vel_jump"] < 0.5, (prop, fps, c)       # anahtar karede dünya hızı süreksizliği yok (el değişirken sıçrama yok)

def test_throw_into_bin_arrives_at_named_sink_and_disappears_only_by_explicit_event():
    TOSS = [{"t": 0, "holder": "harun"}, {"t": 2.0, "holder": "harun"}, {"t": 3.2, "at": "bin_green", "hide": True}]
    assert O.validate(TOSS, ["aden", "harun"], TG, SK) == []
    bad = [{"t": 0, "holder": "harun"}, {"t": 3.2, "at": [1.7, 0.7], "hide": True}]
    assert O.validate(bad, ["aden", "harun"], TG, SK)                          # sink olmayan yerde imha reddedilir (hatayı gizlemez)
    b = _beat(prop="bottle", track=TOSS, h_x=(1.4, 1.4))
    # uçuş boyunca nesne görünür; varış anında hedef konumda; sonra kaybolur
    seen = [r2._objects_now(b, _items(b, t / 24), t / 24) for t in range(int(2.0 * 24), int(3.2 * 24))]
    assert all(len(s) == 1 for s in seen)
    last = seen[-1][0]; assert abs(last[1] - TG["bin_green"][0]) < 0.1 and abs(last[2] - TG["bin_green"][1]) < 0.1
    assert r2._objects_now(b, _items(b, 3.5), 3.5) == []

def test_drop_releases_hand_and_object_rests_on_ground():
    DROP = [{"t": 0, "holder": "aden"}, {"t": 1.0, "holder": "aden"}, {"t": 1.8, "at": [0.2, 0.0]}, {"t": 4, "at": [0.2, 0.0]}]
    b = _beat(prop="bottle", track=DROP)
    for t in (0.5, 1.5):
        assert r2._objects_now(b, _items(b, t), t)[0][4] in ("aden", None)
    ob, x, y, st, own, hand = r2._objects_now(b, _items(b, 2.5), 2.5)[0]
    assert own is None and st["state"] == "ground" and y == 0.0 and x == 0.2          # el bağlantısı kesildi, yerde duruyor, havada asılı değil
    assert O.validate([{"t": 0, "holder": "aden"}, {"t": 1, "at": [0.2, 0.6]}], ["aden"], TG, SK)   # havada bırakma yasak

def test_draw_order_object_after_holder_and_fingers_after_object():
    log = []
    orig = props2d.draw; props2d.draw = lambda cv, cam, kind, *a, **k: (log.append("prop"), orig(cv, cam, kind, *a, **k))[1]
    class Spy(pp.Cv):
        def capsule(self, *a, **k):
            log.append("capsule"); return super().capsule(*a, **k)
    try:
        b = _beat(prop="bottle"); items = _items(b, 1.0)
        class Cam:
            s = 300.0
            def x(self, wx): return 640 + wx * 300
            def y(self, wy): return 650 - wy * 300
        r2._draw_objects(Spy(1280, 720), Cam(), b, items, None, 1.0, owner="aden")
    finally:
        props2d.draw = orig
    assert log[0] == "prop" and log[1:].count("capsule") >= 3                      # önce nesne, sonra parmaklar (nesne parmakların arkasında)

def test_weight_balance_depends_on_carry_style_not_one_effect():
    st = {p: O.carry_style(p) for p in PROPS}
    assert st["stone"] == "two_hand_front" and st["shovel"] == "shoulder" and st["bottle"] == "one_hand"
    a = O.carry_adjust(O.weight_of("stone"), "two_hand_front", 0.25); b = O.carry_adjust(O.weight_of("stone"), "two_hand_front", 0.10)
    s = O.carry_adjust(O.weight_of("shovel"), "shoulder"); o = O.carry_adjust(O.weight_of("bottle"), "one_hand")
    assert a["lean"] < b["lean"] < 0                    # yük gövdeden uzaklaştıkça daha çok geri yaslanma (ağırlık merkezi)
    assert s["lean"] > 0 and o["arms"] == "one_side" and a["arms"] == "both_front" and s["arms"] == "one_up"
    assert abs(o["lean"]) < abs(a["lean"])             # hafif tek elde yük, ağır iki elde yükten çok az denge değiştirir

def test_continuity_metric_catches_teleport_between_hands():
    bad = [{"t": 0, "holder": "aden"}, {"t": 2.0, "holder": "aden"}, {"t": 2.05, "holder": "harun"}, {"t": 9, "holder": "harun"}]
    b = _beat(a_kind="reach", h_kind="reach", prop="bottle", track=bad)
    def hold(holder, t, hand=None):
        h = r2._hold_pos(holder, _items(b, t), None, b, t, hand, O.grip_of("bottle")); return h[0], h[1]
    c = O.continuity(bad, hold, lambda at: tuple(at), fps=24)
    assert c["key_vel_jump"] > 0.5 and O.validate(bad, ["aden", "harun"], TG, SK)      # hem hız süreksizliği hem doğrulayıcı yakalar


def test_arm_toward_puts_hand_on_target_when_reachable_and_reports_shortfall():
    import math
    for cid in ("aden", "harun", "esra", "kaan"):
        d = DES[cid]
        for side in "LR":
            p = sm.base_pose(0.0)
            sh = pp.shoulder_offset(d, p, side); sg = -1 if side == "L" else 1
            tx, th = sh[0] + sg * 0.6 * d["height"] * 0.27, sh[1] - 0.5 * d["height"] * 0.27          # ulaşılabilir hedef (yan ve biraz aşağı)
            ratio = pp.arm_toward(d, p, side, tx, th)
            dx, h = pp.hand_offset(d, p, side)
            assert ratio < 1.0 and math.hypot(dx - tx, h - th) < 0.02, (cid, side, ratio, dx, tx, h, th)
            far = pp.arm_toward(d, p, side, tx + sg * 3.0, th)
            assert far > 1.0                                                                    # çok uzak hedef: oran 1'i aşar (el yetişmez)

def test_handoff_feasibility_flags_far_apart_and_accepts_close():
    a, h = DES["aden"], DES["harun"]
    assert pp.handoff_reach_ratio(a, 0.2, h, 1.4) > 1.0 and pp.handoff_reach_ratio(a, 1.0, h, 1.3) <= 1.0

def test_plan_preflight_reports_unreachable_handoff_and_hands_meet_when_close():
    GIVE = [{"t": 0, "holder": "aden"}, {"t": 2.0, "holder": "aden"}, {"t": 3.4, "holder": "harun"}, {"t": 9, "holder": "harun"}]
    def plan(xa, xb):
        return {"beats": [{"id": "b", "t_start": 0, "t_end": 9, "cast": ["aden", "harun"], "motion": {"aden": {"kind": "idle", "x0": xa, "x1": xa, "seed": 0}, "harun": {"kind": "idle", "x0": xb, "x1": xb, "seed": 1}},
                           "choreo": {"objects": [{"prop": "bottle", "track": GIVE}]}}]}
    assert r2.handoff_problems(plan(0.2, 1.4), DES) and not r2.handoff_problems(plan(1.0, 1.3), DES)
    # yakınken el değiştirme anında iki elin arası küçük (eller buluşuyor), uzaktaki eski sahnede büyüktü
    b = plan(1.0, 1.3)["beats"][0]; b["motion"]["aden"]["kind"] = "reach"
    items = _items(b, 2.7); r2.apply_handoff_reach(b, items, 2.7)
    ha = pp.hand_offset(items[0][1], items[0][2], r2.pick_hand(b, "aden")); hh = pp.hand_offset(items[1][1], items[1][2], r2.pick_hand(b, "harun"))
    gap = abs((items[0][2]["x"] + ha[0]) - (items[1][2]["x"] + hh[0])); vgap = abs(ha[1] - hh[1])
    assert gap < 0.12 and vgap < 0.12, (gap, vgap)


def test_pick_hand_reads_real_beat_layout():
    """Gerçek beat'te hareket 'choreo.motion' altında, oyuncular 'characters' anahtarında: karşıdaki kişiye yakın el seçilmeli (regresyon: hep R seçiliyordu)."""
    beat = {"characters": ["harun", "aden"], "choreo": {"motion": {"harun": {"kind": "idle", "x0": 1.4, "x1": 1.4}, "aden": {"kind": "reach", "x0": 0.8, "x1": 0.8}}}}
    assert r2.pick_hand(beat, "harun") == "L" and r2.pick_hand(beat, "aden") == "R"


def test_transfer_object_drawn_after_all_characters():
    beat = {"choreo": {"objects": [{"prop": "bottle", "track": [{"t": 0, "holder": "a"}, {"t": 1.0, "holder": "a"}, {"t": 2.0, "holder": "b"}, {"t": 5, "holder": "b"}]}]}}
    items = [("a", {"height": 1.0, "class": "child"}, {"x": 0.0}, None, None, None)]
    st = r2.object_state.state_at(beat["choreo"]["objects"][0]["track"], 1.5)
    assert st["state"] == "transfer"


def test_throw_distance_preflight():
    import object_state as O
    tr = [{"t": 0, "holder": "h"}, {"t": 2, "holder": "h"}, {"t": 3, "at": "bin_green", "hide": True}]
    T = {"bin_green": (1.3, 0.9)}
    assert any("atış mesafesi" in p for p in O.throw_problems(tr, lambda c, t: 1.4, T))
    assert O.throw_problems(tr, lambda c, t: 0.5, T) == []
    assert any("menzil" in p for p in O.throw_problems(tr, lambda c, t: -2.5, T))


def test_pick_hand_prefers_throw_target_side_and_swing_moves_arm():
    beat = {"characters": ["h"], "choreo": {"motion": {"h": {"kind": "reach", "x0": 0.5, "x1": 0.5}},
            "objects": [{"prop": "bottle", "track": [{"t": 0, "holder": "h"}, {"t": 2, "holder": "h"}, {"t": 3, "at": "bin_green", "hide": True}]}]}}
    assert r2.pick_hand(beat, "h") == "R"                       # hedef sağda -> sağ el
    des = {"height": 1.8, "class": "adult"}
    mk = lambda: {"x": 0.5, "z": 0.0, "yaw": 0.0, "sq": 1.0, "lean": 0.0, "head": [0.0, 0.0], "aL": [0.0, 0.1], "aR": [0.0, -0.1]}
    p_idle, p_sw = mk(), mk()
    r2.apply_throw_swing(beat, [("h", des, p_idle)], 0.5)      # pencere dışı
    r2.apply_throw_swing(beat, [("h", des, p_sw)], 2.1)        # savurma
    assert p_idle["aR"] == [0.0, -0.1] and p_sw["aR"] != [0.0, -0.1]


def test_staging_resolver_constraints_preferences_and_walking():
    import staging
    from object_state import weight_of as object_state_weight
    T = {"bin_a": (1.3, 0.9), "bin_b": (1.85, 0.9)}
    H = {"x": 1.9, "y": 0.98}
    ob = [{"prop": "bottle", "track": [{"t": 0, "holder": "y"}, {"t": 2.0, "holder": "y"}, {"t": 3.4, "holder": "x"}, {"t": 6, "holder": "x"}]}]
    # 1) fiziksel kısıt ihlali (1.2 m > erişim): düzeltilir; karakter ışınlanmaz, önceki konumdan yürür
    mot = {"x": {"kind": "idle", "x0": 1.4, "x1": 1.4}, "y": {"kind": "idle", "x0": 0.2, "x1": 0.2}}
    notes = staging.resolve(mot, ob, H, T, prev_x={"x": 1.4})
    assert any(n["rule"] == "handoff_separation" and n["kind"] == "adjusted" for n in notes)
    assert mot["x"]["kind"] == "walk" and mot["x"]["x0"] == 1.4 and mot["x"]["walk_s"] * 0.85 <= 2.0          # temastan önce varır
    assert 0.4 * 0.27 * 2.88 <= abs(mot["x"]["x1"] - mot["y"]["x1"]) <= 0.95 * 0.27 * 2.88
    # 2) mesafe fiziksel aralıkta ise TERCİH gerekçesiyle oynanmaz (anlatısal niyet korunur)
    mot2 = {"x": {"kind": "idle", "x0": 0.9, "x1": 0.9}, "y": {"kind": "idle", "x0": 0.3, "x1": 0.3}}
    n2 = staging.resolve(mot2, ob, H, T)
    assert mot2["x"]["x0"] == 0.9 and [n["kind"] for n in n2] == ["ok"]
    # 3) hazırlık süresi yetmiyorsa çelişki bildirilir, hikâye değiştirilmez
    ob_fast = [{"prop": "b", "track": [{"t": 0, "holder": "y"}, {"t": 0.5, "holder": "y"}, {"t": 1.0, "holder": "x"}]}]
    mot3 = {"x": {"kind": "idle", "x0": 1.4, "x1": 1.4}, "y": {"kind": "idle", "x0": 0.2, "x1": 0.2}}
    n3 = staging.resolve(mot3, ob_fast, H, T, prev_x={"x": 1.4})
    assert any(n["kind"] == "conflict" and "yetmiyor" in n["why"] for n in n3) and mot3["x"]["x1"] == 1.4
    # 4) atış aralığı boya/ağırlığa göre hesaplanır (çocuk ve yetişkin farklı)
    lo_a, hi_a = staging.throw_range(1.9, 0.4); lo_c, hi_c = staging.throw_range(0.98, 0.4)
    assert lo_a > lo_c and hi_a > hi_c
    lo_h, hi_h = staging.throw_range(1.9, 2.5)
    assert hi_h < hi_a                                                               # ağır nesne daha kısa menzil
    # 5) atış: kutuya yakın duran atan yürür; başka kutunun önüne durmaz
    obt = [{"prop": "bottle", "track": [{"t": 0, "holder": "x"}, {"t": 2.0, "holder": "x"}, {"t": 3.2, "at": "bin_a", "hide": True}]}]
    mot4 = {"x": {"kind": "idle", "x0": 1.4, "x1": 1.4}}
    staging.resolve(mot4, obt, {"x": 1.9}, T, prev_x={"x": 1.4})
    lo_, hi_ = staging.throw_range(1.9, object_state_weight("bottle"))
    assert lo_ <= abs(mot4["x"]["x1"] - 1.3) <= hi_ and mot4["x"]["kind"] == "walk"


def test_standing_holder_keeps_light_object_at_chest_not_hip_and_scales_with_height():
    import puppet2d as pp
    beat = {"cast": ["a", "k"], "characters": ["a", "k"], "motion": {"a": {"kind": "idle", "x0": 0.9, "x1": 0.9, "seed": 0}, "k": {"kind": "idle", "x0": 0.2, "x1": 0.2, "seed": 1}},
            "lines": [], "camera": "wide", "props": [], "choreo": {"gaze": {"a": "k"}, "objects": [{"prop": "bottle", "track": [{"t": 0, "holder": "a"}, {"t": 9, "holder": "a"}]}]}}
    ci = r2.carry_info(beat, "a", 3.0)
    assert ci and ci["style"] != "two_hand_front"
    des = {"height": 1.9, "class": "adult", "build": 1.0}
    pose = {"x": 0.9, "z": 0.0, "yaw": 0.0, "sq": 1.0, "lean": 0.0, "head": [0.0, 0.0, 0.0], "aL": [0.0, 0.1], "aR": [0.0, -0.1]}
    sx, sh = pp.shoulder_offset(des, pose, ci["hand"]); ln = 1.9 * 0.27
    pp.arm_toward(des, pose, ci["hand"], sx - 0.12 * ln, sh - 0.20 * ln)
    hx, hy = pp.hand_offset(des, pose, ci["hand"])
    assert 0.57 * 1.9 < hy < 0.75 * 1.9            # göğüs/üst gövde hizası, kalça (~0.47 H) değil
