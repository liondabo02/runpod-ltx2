import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import task_observer as to, support_workers as sw


class T(unittest.TestCase):
    def test_observer_dedup_and_review(self):
        d = tempfile.mkdtemp(); to.OBS = os.path.join(d, "o"); to.IMP = os.path.join(d, "i")
        to.log("render", "friction", "kareler eski kaldı", "klasörü yeniden adlandır")
        to.log("render", "friction", "Kareler eski kaldı", "")
        self.assertEqual(len(to._all()), 1); self.assertEqual(to._all()[0]["count"], 2)
        self.assertEqual(len(to.review()), 1); self.assertEqual(len(to.review()), 0)

    def test_workers(self):
        ep = tempfile.mkdtemp()
        json.dump({"beats": [{"t_start": 0, "t_end": 500, "speaker": "a"}]}, open(os.path.join(ep, "beat_sheet.json"), "w"))
        r = sw.run_all(ep)
        self.assertEqual(json.load(open(r["finance"]))["status"], "PASSED")
        self.assertTrue(json.load(open(r["analytics"]))["meets_480s"])
        self.assertEqual(json.load(open(r["rights"]))["status"], "REVIEW_REQUIRED")  # müzik manifesti yok
        self.assertTrue(json.load(open(r["distribution"]))["blocked_by_rights"])


class TShorts(unittest.TestCase):
    def test_window_prefers_busy_part(self):
        import shorts_worker as sh
        beats = [{"t_start": i * 10, "t_end": i * 10 + 10} for i in range(30)]
        beats[20].update(line="x", fx=["burst"], emotion="surprise")
        w = sh.pick_window(beats, 40)
        self.assertTrue(w["t0"] <= 200 < w["t1"]); self.assertEqual(w["t1"] - w["t0"], 40)


if __name__ == "__main__":
    unittest.main()
