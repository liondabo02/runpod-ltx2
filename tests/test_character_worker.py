import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import character_worker as cw

BIBLE = {"characters": [
    {"id": "pelin", "name": "Pelin", "age": 5, "role": "kız", "look": "sarı yağmurluk"},
    {"id": "tosun", "name": "Tosun", "age": 4, "role": "kirpi", "look": "dikenli"},
    {"id": "nine", "name": "Bulut Nine", "age": 70, "role": "nine"}]}


class T(unittest.TestCase):
    def test_sanitize_clamps(self):
        s = cw.sanitize({"class": "child", "height_m": 9, "eye_scale": 5,
                         "palette": {"shirt": [2, -1, 0.5], "bogus": [1, 1, 1]}}, BIBLE["characters"][0])
        self.assertEqual(s["height_m"], 1.55); self.assertEqual(s["eye_scale"], 1.4)
        self.assertEqual(s["palette"]["shirt"], [1.0, 0.0, 0.5, 1.0]); self.assertNotIn("bogus", s["palette"])

    def test_default_on_llm_failure_and_nonhuman_flag(self):
        def bad(*a, **k): raise RuntimeError("x")
        s = cw.design(BIBLE["characters"][1], bad)
        self.assertEqual(s["design_source"], "default"); self.assertEqual(s["class"], "toddler")
        self.assertTrue(s["humanoid_approximation"])

    def test_run_with_fake_backend_and_lock(self):
        d = tempfile.mkdtemp()
        llm = lambda *a, **k: {"class": "child", "height_m": 1.1, "palette": {"shirt": [1, .8, 0]}}
        def be(plan, job, ev):
            ids = json.load(open(plan))["cast"]
            return {"status": "PASSED", "artifacts": [{"cast": i, "path": f"character-model/{i}.glb", "sha256": "ab"} for i in ids]}
        r = cw.run(d, BIBLE, llm, be)
        self.assertEqual(r["status"], "PASSED"); self.assertIn("tosun", r["approximations"])
        self.assertIn("model_sha256", BIBLE["characters"][0]["identity_lock"])
        # kilit: ikinci çalışmada LLM çağrılmaz
        def boom(*a, **k): raise AssertionError("tekrar tasarlandı")
        cw.run(d, BIBLE, boom, be)

    def test_blocked_backend(self):
        d = tempfile.mkdtemp()
        r = cw.run(d, {"characters": [BIBLE["characters"][0]]}, lambda *a, **k: {},
                   lambda p, j, e: {"status": "BLOCKED", "blocked": [{"code": "BLENDER_MISSING"}]})
        self.assertEqual(r["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
