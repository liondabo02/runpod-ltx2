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

if __name__ == "__main__":
    unittest.main()
