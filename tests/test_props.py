import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import props2d, scenes2d as sc, puppet2d as pp


class T(unittest.TestCase):
    def test_extract(self):
        self.assertEqual(props2d.extract("Kaan avucunda ışık veren tohum tutuyor, taş yolda"), ["seed", "stone"])
        self.assertEqual(props2d.extract("sakin bekler"), [])

    def test_draw_all_kinds(self):
        for k in ("seed", "stone", "hat", "flower", "bottle", "drops", "leaves", "shovel", "mic", "balloon", "lantern", "kite"):
            cv = pp.Cv(); cam = sc.Cam(0, 0.95, 1.0)
            wx, wy = props2d.place(k, [-0.6, 0.6], [1.1, 1.0], 1.0, 1.0, 6.0)
            props2d.draw(cv, cam, k, wx, wy, 1.0, 0)
            self.assertIsNotNone(cv.done())


class TFx(unittest.TestCase):
    def test_fx(self):
        self.assertEqual(props2d.fx_kinds(["surprise", "run"]), ["burst", "speed"])
        for k in ("burst", "stars", "speed"):
            cv = pp.Cv(); cam = sc.Cam(0, 0.95, 1.0)
            props2d.draw_fx(cv, cam, k, 0.0, 1.2, 1.0, 0.5)
            self.assertIsNotNone(cv.done())

    def test_room_scene(self):
        cv = pp.Cv(); sc.scene_back(cv, "room", sc.Cam(0, 0.95, 1.0), 0.0)
        self.assertIsNotNone(cv.done())


class TNew(unittest.TestCase):
    def test_new_scenes_and_rules(self):
        import shot_planner as sp
        for k in ("stage", "village", "garden"):
            cv = pp.Cv(); cam = sc.Cam(0, 0.95, 1.0)
            sc.scene_back(cv, k, cam, 1.0); sc.scene_front(cv, k, cam, 1.0)
            self.assertIsNotNone(cv.done())
        self.assertEqual(sp.scene_type("sahne", []), "stage")
        self.assertEqual(sp.scene_type("koy_meydani", []), "village")
        self.assertEqual(sp.scene_type("bahce", []), "garden")
        self.assertEqual(props2d.extract("mikrofon tutuyor ve balon uçuruyor"), ["mic", "balloon"])
