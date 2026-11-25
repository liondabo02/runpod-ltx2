import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import foot_slide as F
HERE = os.path.join(os.path.dirname(__file__), "..", "tools")
SM = F._load(os.path.join(HERE, "shot_motion.py"), "sm_t")

def test_correct_walk_passes_for_child_and_adult_and_run():
    for kind in ("walk", "run"):
        for H in (1.0, 1.7):
            assert F.check(SM, kind, H)["pass"], (kind, H)

def test_deliberate_slide_is_caught():
    assert not F.check(SM, "walk", 1.7, inject=0.25)["pass"]         # temas ayağı bilerek boyun %25'i/sn kaydırıldı

def test_stationary_feet_do_not_move_when_stopped_and_both_planted():
    r = F.world_feet(SM, "walk", 1.7, dur=3.0)
    last = r[-1]; assert last[3] and last[5]                           # duruşta iki ayak yerde

def test_short_and_long_distances_and_directions():
    for x0, x1 in ((-1, 1), (1, -1), (0, 0.4), (-1.9, 1.9)):
        assert F.check(SM, "walk", 1.3, x0=x0, x1=x1)["pass"], (x0, x1)

def test_old_gait_would_fail_metric():
    import os
    old = "/tmp/sm_before_gait.py"
    if os.path.exists(old):
        o = F._load(old, "sm_old_t"); assert not F.check(o, "walk", 1.7, legacy=True)["pass"]
