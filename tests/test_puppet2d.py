import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import puppet2d as pp, render2d as r2, shot_planner as sp


class T(unittest.TestCase):
    def test_design_rules(self):
        d = pp.derive_design({"id": "x", "name": "Tosun", "role": "kirpi", "age": 4}, {})
        self.assertEqual(d["species"], "hedgehog")
        d = pp.derive_design({"id": "y", "name": "Nine", "role": "nine", "age": 70}, {})
        self.assertEqual((d["hair_style"], d["accessory"]), ("bun", "glasses"))

    def test_frame_all_scenes_and_mouths(self):
        d = tempfile.mkdtemp()
        beats = [{"t_start": 0, "t_end": 10, "location": loc, "characters": ["a", "b"], "action": "a zıplar b el sallar", "dialogue": "", "camera": cam}
                 for loc, cam in (("bahce", "genel plan"), ("cati", "yakın"), ("oda", "orta"))]
        for i, b in enumerate(beats):
            b["t_start"], b["t_end"] = i * 10, i * 10 + 10
        json.dump({"beats": beats}, open(os.path.join(d, "beat_sheet.json"), "w"))
        bible = {"characters": [{"id": "a", "name": "Ali", "age": 6}, {"id": "b", "name": "Bo", "age": 40}], "locations": [{"id": "cati", "name": "çatı"}, {"id": "oda", "name": "oda"}]}
        plan = sp.plan(d, bible, d, 0, 30)
        des = {c["id"]: pp.derive_design(c, {}) for c in bible["characters"]}
        for t in (2.0, 12.0, 22.0):
            im = r2.frame(plan, des, t)
            self.assertEqual(im.size, (1280, 720))
        cv = pp.Cv()
        for L in "ABCDEFGHX":
            pp.draw_mouth(cv, 300, 300, 60, 30, L)

    def test_render_window_resumes(self):
        d = tempfile.mkdtemp()
        json.dump({"beats": [{"t_start": 0, "t_end": 2, "location": "bahce", "characters": ["a"], "action": "", "dialogue": "", "camera": "genel"}]}, open(os.path.join(d, "beat_sheet.json"), "w"))
        bible = {"characters": [{"id": "a", "name": "Ali", "age": 6}], "locations": []}
        plan = sp.plan(d, bible, d, 0, 1)
        des = {"a": pp.derive_design(bible["characters"][0], {})}
        s1 = r2.render_window(plan, des, os.path.join(d, "f"), workers=1)
        s2 = r2.render_window(plan, des, os.path.join(d, "f"), workers=1)
        self.assertEqual(s1["rendered"], 12); self.assertEqual(s2["rendered"], 0)


if __name__ == "__main__":
    unittest.main()
