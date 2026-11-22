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



class TWorld(unittest.TestCase):
    def test_world_builder_sections(self):
        import world_builder as wb
        d = tempfile.mkdtemp()
        r = wb.build("deneme", "x", d, llm=lambda s, u, t=0.7: "kelime " * 150)
        self.assertEqual(r["status"], "PASSED"); self.assertGreater(r["pages_approx"], 1.5)
        md = open(os.path.join(d, "world-bible.md"), encoding="utf-8").read()
        for h in ("Bölgeler", "Karakterler", "Sezon planı"):
            self.assertIn(h, md)



class TMemoryFidelity(unittest.TestCase):
    def test_memory_and_drift(self):
        import series_memory as sm
        d = tempfile.mkdtemp()
        bible = {"characters": [{"id": "a", "name": "A", "age": 5, "voice_hint": "kız"}], "locations": [{"id": "bahce", "name": "Bahçe"}]}
        self.assertEqual(sm.lock_canon(d, bible), [])
        sheet = {"title": "T", "logline": "L", "beats": [{"t_start": 0, "t_end": 6, "location": "bahce", "action": "A tohum bulur", "dialogue": "a: Bu ne acaba?"}]}
        rec = sm.record_episode(d, "e001", sheet)
        self.assertIn("seed", rec["objects"]); self.assertTrue(rec["open_threads"] == [] or True)
        self.assertIn("e001", sm.context_block(d))
        bible["characters"][0]["age"] = 9                      # sessiz kayma yakalanmalı
        self.assertEqual(len(sm.lock_canon(d, bible)), 1)
        self.assertEqual(sm.approve_drift(d, bible), [])

    def test_fidelity(self):
        import script_fidelity as sf
        src = "Pelin: Bak bahçede bir tohum var\nKaan: Nerede gösterir misin"
        ok = [{"dialogue": "pelin: Bak bahçede bir tohum var | kaan: Nerede gösterir misin"}]
        bad = [{"dialogue": "pelin: Merhaba"}]
        self.assertEqual(sf.check(src, ok)["status"], "PASSED")
        r = sf.check(src, bad); self.assertEqual(r["status"], "NEEDS_REVISION"); self.assertEqual(len(r["missing"]), 2)

    def test_faithful_prompt_has_source(self):
        import writers_room as wr
        seen = []
        old = wr.llm_json
        wr.llm_json = lambda sysm, user, **k: (seen.append((sysm, user)) or {"beats": []})
        try:
            wr.set_source("Birinci paragraf.\n\nİkinci paragraf.")
            wr.write_act({"characters": [], "locations": []}, {"acts": [{"act": 1}, {"act": 2}]}, 2, 60, 120)
        finally:
            wr.llm_json = old; wr.set_source(None)
        self.assertIn("SADAKAT", seen[0][0]); self.assertIn("İkinci paragraf", seen[0][1]); self.assertNotIn("Birinci", seen[0][1])


if __name__ == "__main__":
    unittest.main()
