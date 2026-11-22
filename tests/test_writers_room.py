import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import writers_room as wr
from validate_beat_sheet import validate

BIBLE = {"series_id": "t", "title": "T", "age_band": "2-5",
         "characters": [{"id": "a"}, {"id": "b"}], "locations": [{"id": "park"}]}


def good_beats(t0, t1):
    out, t, i = [], t0, 0
    while t < t1:
        e = min(t + 8, t1)
        out.append({"t_start": t, "t_end": e, "scene_id": "s", "location": "park", "characters": ["a", "b"],
                    "action": f"eylem {t} yeni olay {i}", "dialogue": f"merhaba {i} arkadaş nasılsın", "emotion": {"valence": .5, "arousal": .5, "intensity": .5},
                    "camera": "orta", "sound": "müzik"})
        t, i = e, i + 1
    return out


BIBLE2 = {"characters": [{"id": "pelin", "name": "Pelin"}, {"id": "tosun", "name": "Tosun"}]}


class Fake:
    def __init__(self): self.calls = 0
    def __call__(self, system, user, temperature=0.7):
        self.calls += 1
        if "dil editörü" in system:
            return user.split("aynı yapıda döndür: ", 1)[1]
        if "eleştirmen" in system:
            return json.dumps({"scores": {"merak": 18, "yas_uygunluk": 18, "kimlik_surekliligi": 18,
                                          "eylem_cesitliligi": 13, "ses_duygu": 13, "guvenlik": 10}, "findings": []})
        if "Toplam" in user:
            return json.dumps({"title": "T", "logline": "L", "acts": [{"act": i} for i in range(1, 7)]})
        import re
        m = re.search(r"Zaman aralığı: (\d+)-(\d+)", user)
        return json.dumps({"beats": good_beats(int(m.group(1)), int(m.group(2)))})


class Flaky(Fake):
    def __call__(self, system, user, temperature=0.7):
        self.calls += 1
        if self.calls % 3 == 1:
            return "üzgünüm, JSON veremem"
        return Fake.__call__(self, system, user, temperature)


class T(unittest.TestCase):
    def setUp(self):
        self._ll, self._sl = wr.llm_call, wr.time.sleep

    def tearDown(self):
        wr.llm_call, wr.time.sleep = self._ll, self._sl

    def test_survives_garbage_responses(self):
        wr.time.sleep = lambda *_: None
        wr.llm_call = Flaky()
        with tempfile.TemporaryDirectory() as d:
            sheet, hist = wr.run(BIBLE, "fikir", 480, d)
            self.assertTrue(os.path.exists(os.path.join(d, "beat_sheet.json")))
            self.assertEqual(hist[-1]["validator_errors"], [])

    def test_pipeline(self):
        wr.llm_call = Fake()
        with tempfile.TemporaryDirectory() as d:
            sheet, hist = wr.run(BIBLE, "fikir", 480, d)
            self.assertEqual(hist[-1]["validator_errors"], [])
            self.assertEqual(sheet["status"], "DRAFT_FOR_OWNER_APPROVAL")
            self.assertTrue(os.path.exists(os.path.join(d, "beat_sheet.json")))

    def test_validator_catches_gap_and_unknown_char(self):
        b = good_beats(0, 480); b[3]["t_start"] += 5; b[5]["characters"] = ["zzz"]
        errs, _ = validate({"beats": b}, BIBLE, 480)
        self.assertTrue(any("boşlu" in e for e in errs))
        self.assertTrue(any("zzz" in e for e in errs))

    def test_validator_short(self):
        errs, _ = validate({"beats": good_beats(0, 100)}, BIBLE, 480)
        self.assertTrue(any("hedef" in e for e in errs))

    def test_safety_requires_note(self):
        b = good_beats(0, 480); b[0]["action"] = "Kaan ipi tutuyor"
        errs, warns = validate({"beats": b}, BIBLE, 480)
        self.assertTrue(any("safety_note" in e for e in errs))

    def test_normalize_fixes_times(self):
        bad = [{"t_start": 0, "t_end": 30, "action": "a"}, {"t_start": 0, "t_end": 3, "action": "b"}, {"action": "c"}]
        out = wr.normalize_act(bad, 80, 120, 2, "park", {"park"})
        self.assertEqual(out[0]["t_start"], 80.0); self.assertEqual(out[-1]["t_end"], 120.0)
        for a, b in zip(out, out[1:]): self.assertEqual(a["t_end"], b["t_start"])
        self.assertTrue(all(x["scene_id"] and x["sound"] and x["location"] == "park" for x in out))

    def test_silent_is_error(self):
        b = good_beats(0, 480)
        for x in b: x["dialogue"] = ""
        errs, _ = validate({"beats": b}, BIBLE, 480)
        self.assertTrue(any("diyalog çok az" in e for e in errs))

    def test_near_duplicate_action(self):
        b = good_beats(0, 480); b[2]["action"] = b[1]["action"] + " ve"
        errs, _ = validate({"beats": b}, BIBLE, 480)
        self.assertTrue(any("tekrar" in e or "aynı eylem" in e for e in errs))

    def test_fix_names_and_empty_chars(self):
        b = [{"action": "Pelin ve Tosan koşar", "dialogue": "Tosan: Hadi! tosan küçük"}]
        n = wr.fix_names(b, BIBLE2)
        self.assertEqual(b[0]["action"], "Pelin ve Tosun koşar"); self.assertEqual(b[0]["dialogue"], "Tosun: Hadi! tosan küçük"); self.assertGreaterEqual(n, 2)
        g = [{"action": "Gelin buraya! Pelin geldi", "dialogue": ""}]; wr.fix_names(g, BIBLE2)
        self.assertEqual(g[0]["action"], "Gelin buraya! Pelin geldi")   # gerçek kelime bozulmamalı
        bb = good_beats(0, 480); bb[-1]["characters"] = []
        errs, _ = validate({"beats": bb}, BIBLE, 480)
        self.assertFalse(any("characters" in e for e in errs))

    def test_proofread_keeps_structure(self):
        beats = good_beats(0, 40)
        orig_times = [(b["t_start"], b["t_end"]) for b in beats]
        def llm(system, user, temperature=0.7):
            return json.dumps({"beats": [{"i": b_i, "action": "düzeltilmiş eylem metni burada", "dialogue": ""} for b_i in range(len(beats))]})
        wr.llm_call = llm; wr.time.sleep = lambda *_: None
        wr.proofread(beats)
        self.assertEqual([(b["t_start"], b["t_end"]) for b in beats], orig_times)
        self.assertEqual(len(beats), 5)

    def test_repeat_action(self):
        b = good_beats(0, 480); b[1]["action"] = b[0]["action"]; b[1]["dialogue"] = "x y z"
        errs, _ = validate({"beats": b}, BIBLE, 480)
        self.assertTrue(any("aynı eylem" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
