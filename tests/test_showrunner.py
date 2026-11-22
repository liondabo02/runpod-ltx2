import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import showrunner as sr, writers_room as wr
from test_writers_room import Fake

BIBLE_RAW = {"title": "Deneme Dizisi", "tone": "sıcak", "age_band": "3-6", "visual_style": {"look": "yumuşak"},
             "characters": [{"id": "a", "name": "A", "age": 5, "role": "x", "voice_hint": "kız çocuk"},
                            {"id": "b", "name": "B", "age": 4, "role": "y", "voice_hint": "erkek çocuk"}],
             "locations": [{"id": "park", "name": "Park"}]}


class Mgr(Fake):
    def __call__(self, system, user, temperature=0.7):
        if "yaratıcı direktör" in system:
            return json.dumps(BIBLE_RAW)
        return Fake.__call__(self, system, user, temperature)


class T(unittest.TestCase):
    def setUp(self):
        self._vr, self._ll, self._sl, self._ar = sr.vw.run, wr.llm_call, wr.time.sleep, sr.aw.run
        sr.aw.run = lambda out: {'status': 'PASSED', 'duration_s': 480, 'voiced_lines': 3}
        self._rr = sr.rw.run; sr.rw.run = lambda *a, **k: {'status': 'BLOCKED', 'error': 'FAKE'}; self._cr = sr.cw.run; sr.cw.run = lambda d, b: {'status': 'PASSED', 'characters': [], 'approximations': []}

    def tearDown(self):
        sr.vw.run, wr.llm_call, wr.time.sleep, sr.aw.run = self._vr, self._ll, self._sl, self._ar
        sr.cw.run = self._cr; sr.rw.run = self._rr

    def test_new_series_then_next_episode(self):
        wr.llm_call = Mgr(); wr.time.sleep = lambda *_: None
        sr.vw.run = lambda out, bible: {'status': 'PASSED', 'lines': 3, 'problems': []}
        with tempfile.TemporaryDirectory() as d:
            r1 = sr.run("a ve b parkta", None, 480, d)
            self.assertEqual(r1["series_id"], "deneme-dizisi"); self.assertEqual(r1["episode"], "e001")
            r2 = sr.run("ikinci bölüm", "deneme-dizisi", 480, d)
            self.assertEqual(r2["episode"], "e002")
            self.assertEqual(r2["steps"][0]["status"], "REUSED")   # karakterler korundu
            led = open(os.path.join(d, "deneme-dizisi", "ledger.jsonl"), encoding="utf-8").read()
            self.assertIn("NOT_CONNECTED", led)
            self.assertIn('"worker": "voice"', led)
            self.assertIn("sha256", led)

    def test_voice_engine_missing_is_blocked_not_crash(self):
        wr.llm_call = Mgr(); wr.time.sleep = lambda *_: None
        def boom(out, bible): raise ImportError('edge_tts yok')
        sr.vw.run = boom
        with tempfile.TemporaryDirectory() as d:
            r = sr.run('x', None, 480, d)
            self.assertIn('BLOCKED', [s['status'] for s in r['steps']])

    def test_bad_bible_fails_closed(self):
        bad = dict(BIBLE_RAW); bad["characters"] = [{"id": "A B"}]
        class Bad(Fake):
            def __call__(s, system, user, temperature=0.7): return json.dumps(bad)
        wr.llm_call = Bad(); wr.time.sleep = lambda *_: None
        with tempfile.TemporaryDirectory() as d:
            r = sr.run("x", None, 480, d)
            self.assertEqual(r["steps"][0]["status"], "FAILED")

    def test_slug(self):
        self.assertEqual(sr.slug("Bulut Bahçesi!"), "bulut-bahcesi")


if __name__ == "__main__":
    unittest.main()
