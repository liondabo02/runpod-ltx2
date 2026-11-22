import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import lessons

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); lessons.MEM = self.d
    def test_dedupe_and_owner_first(self):
        lessons.add("writers_room", "Kısa yaz", count=1); lessons.add("writers_room", "kısa yaz!", count=1)
        self.assertEqual(lessons.load("writers_room")[0]["count"], 2)
        lessons.add("director", "Sahip kuralı", source="owner", count=5)
        top = lessons.top("writer")
        self.assertEqual(top[0]["lesson"], "Sahip kuralı")
        self.assertIn("SAHİBİN", lessons.prompt_block("writer"))
    def test_retire_and_cap(self):
        for i in range(60):
            lessons.add("x", "ders %d" % i)
        self.assertLessEqual(len(lessons.load("x")), lessons.MAX_PER_WORKER)
        self.assertGreaterEqual(lessons.retire("x", "ders 5"), 0)
    def test_empty_block(self):
        self.assertEqual(lessons.prompt_block("writer"), "")
    def test_improver_and_daemon(self):
        import studio_improver, studio_daemon, studio_enqueue
        out = os.path.join(self.d, "out"); os.makedirs(os.path.join(out, "e1")); os.makedirs(os.path.join(out, "e2"))
        for e in ("e1", "e2"):
            json.dump({"errors": ["diyalog çok az"]}, open(os.path.join(out, e, "v.json"), "w", encoding="utf-8"), ensure_ascii=False)
        studio_improver.REPORTS = os.path.join(self.d, "rep")
        r = studio_improver.run(out); self.assertEqual(len(r["added"]), 1)
        self.assertTrue(os.path.exists(r["report"]))
        studio_enqueue.Q = studio_daemon.Q = os.path.join(self.d, "q")
        jid = studio_enqueue.enqueue("test"); studio_daemon.recover()
        self.assertEqual(studio_daemon.run_job(studio_daemon.next_job(), runner=lambda j: {"ok": 1}), "done")
        jid = studio_enqueue.enqueue("bad")
        def boom(j): raise ValueError("x")
        self.assertEqual(studio_daemon.run_job(studio_daemon.next_job(), runner=boom), "failed")
        self.assertIsNone(studio_daemon.next_job())
if __name__ == "__main__":
    unittest.main()


class TLong(unittest.TestCase):
    def test_split_and_need(self):
        import writers_room as w
        b = [{"t_start": 0, "t_end": 26, "action": "Kaan koşar", "dialogue": "a: bir | b: iki | a: üç"}]
        r = w.split_long(b, 0, 26)
        self.assertEqual(len(r), 3)
        self.assertEqual(sum(1 for x in r if x["dialogue"]), 3)
        self.assertNotEqual(r[0]["action"], r[1]["action"])
        self.assertEqual(w.need_beats(0, 80), 11)


class TResume(unittest.TestCase):
    def test_acts_resume_after_failure(self):
        import writers_room as w, tempfile
        w.say = lambda *_: None
        calls = []
        def fake_act(bible, outline, act_no, t0, t1, notes=None, tail=None):
            calls.append(act_no)
            if act_no == 3 and calls.count(3) == 1:
                raise RuntimeError("LLM boş")
            return [{"t_start": 0, "t_end": 7, "action": "a%d_%d" % (act_no, k), "dialogue": "", "location": "l", "characters": []} for k in range(need(t0, t1))]
        need = w.need_beats
        w.write_act = fake_act
        outline = {"acts": [{"act": i} for i in (1, 2, 3)]}
        d = tempfile.mkdtemp(); cache = w._cache_load(d, "k")
        bible = {"locations": [{"id": "l"}], "characters": []}
        with self.assertRaises(RuntimeError):
            w.build(bible, outline, 240, cache=cache, out_dir=d)
        cache = w._cache_load(d, "k"); calls.clear()
        beats = w.build(bible, outline, 240, cache=cache, out_dir=d)
        self.assertEqual(calls, [3])                 # 1. ve 2. perde yeniden yazılmadı
        self.assertGreater(len(beats), 20)
