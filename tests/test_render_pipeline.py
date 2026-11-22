import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import shot_motion as sm, shot_planner as sp, render_worker as rw, character_worker as cw


class T(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(sm.classify("Pelin koşup takip eder"), "run")
        self.assertEqual(sm.classify("el sallar"), "wave")
        self.assertEqual(sm.classify("çiçeğe doğru yürür"), "walk")
        self.assertEqual(sm.classify("hiçbir şey"), "idle")

    def test_per_character_motion(self):
        a = "Pelin zıplar, Tosun çiçeği kaldırır."
        self.assertEqual(sm.motion_for("pelin", a, "Pelin"), "jump")
        self.assertEqual(sm.motion_for("tosun", a, "Tosun"), "reach")

    def test_poses_finite_all_kinds(self):
        for k in [x for x, _ in sm.KINDS] + ["idle"]:
            for t in (0, 0.5, 3.3, 9.99):
                p = sm.pose_at(k, t, 10, 3, 0.0, 1.8, 1.2, 0.6, speaking=True)
                flat = [p["x"], p["y"], p["z"], p["yaw"], p["lean"], p["lL"], p["lR"], *p["head"], *p["aL"], *p["aR"]]
                self.assertTrue(all(abs(v) < 10 for v in flat), (k, t))

    def test_offsets_no_overlap(self):
        items = sp.assign_offsets([{"beat": 0, "duration_s": 2.0}, {"beat": 0, "duration_s": 1.0}, {"beat": 1, "duration_s": 1.0}])
        self.assertAlmostEqual(items[1]["start_s"], 2.5); self.assertAlmostEqual(items[2]["start_s"], 0.2)

    def test_plan(self):
        d = tempfile.mkdtemp()
        beats = [{"t_start": 0, "t_end": 10, "location": "bahce", "characters": ["a", "b"], "action": "a koşar", "dialogue": "", "camera": "genel plan"},
                 {"t_start": 10, "t_end": 20, "location": "cati", "characters": ["a"], "action": "el sallar", "dialogue": "", "camera": "yakın"}]
        json.dump({"beats": beats}, open(os.path.join(d, "beat_sheet.json"), "w"))
        bible = {"characters": [{"id": "a", "name": "Ali"}, {"id": "b", "name": "Bo"}], "locations": [{"id": "cati", "name": "Çatı"}]}
        p = sp.plan(d, bible, d, 0, 20)
        self.assertEqual([b["scene"] for b in p["beats"]], ["garden", "roof"])
        self.assertEqual(p["beats"][1]["camera"], "close")
        self.assertEqual(rw.split_by_scene({"beats": beats}, 0, 20), [[0.0, 10.0, "bahce"], [10.0, 20.0, "cati"]])

    def test_default_palettes_differ(self):
        self.assertNotEqual(cw.default_palette("pelin")["shirt"], cw.default_palette("tosun")["shirt"])


if __name__ == "__main__":
    unittest.main()
