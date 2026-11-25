import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import foot_slide as F, motion_continuity as M
SM = F._load(os.path.join(os.path.dirname(__file__), "..", "tools", "shot_motion.py"), "sm_ph")

def test_walk_and_run_have_anticipation_and_recovery():
    for kind in ("walk", "run"):
        for H in (1.0, 1.7):
            s = M.phase_signature(SM, kind, H)
            assert s["anticipation"] and s["recovery_overshoot"], (kind, H, s)

def test_no_pose_pops_in_start_and_stop():
    for kind in ("walk", "run"):
        for H in (1.0, 1.7):
            w, _ = M.jumps(SM, kind, H)
            assert w["yaw"] < 0.30 and w["lean"] < 0.06 and w["sq"] < 0.08, (kind, H, w)   # eski yürüyüş: yaw tek karede 0.55 sıçrıyordu

def test_phases_keep_feet_planted():
    for kind in ("walk", "run"):
        for H in (1.0, 1.7):
            assert F.check(SM, kind, H)["pass"], (kind, H)

def test_phase_length_depends_on_character():
    # çocuk ve yetişkin için hazırlık farklı sürede biter (aynı eğri değil)
    def t_peak(H):
        v = [(SM.pose_at("walk", i / 120, 3.0, 0, -1, 1, H, 0.5 * H)["lean"], i) for i in range(40)]
        return min(v)[1]
    assert t_peak(1.0) != t_peak(1.7)

def test_old_version_had_pop():
    old = "/tmp/sm_before_phases.py"
    if os.path.exists(old):
        w, _ = M.jumps(F._load(old, "sm_o2"), "walk", 1.7); assert w["yaw"] > 0.4

def test_blinks_are_desynchronised_between_characters():
    import itertools
    fps = 24; n = 24 * 20
    seqs = {s: [SM.blink(i / fps, s) for i in range(n)] for s in range(4)}
    for a, b in itertools.combinations(seqs, 2):
        both = sum(1 for x, y in zip(seqs[a], seqs[b]) if x > 0.5 and y > 0.5)
        either = sum(1 for x, y in zip(seqs[a], seqs[b]) if x > 0.5 or y > 0.5)
        assert either > 0 and both / either < 0.5, (a, b, both, either)    # göz kırpmaların yarısından azı çakışır
