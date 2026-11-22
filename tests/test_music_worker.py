import json, os, sys, tempfile, unittest, wave
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import music_worker as mw


class T(unittest.TestCase):
    def test_theme_stable_and_different(self):
        self.assertEqual(mw.theme("a"), mw.theme("a"))
        self.assertTrue(any(mw.theme(x) != mw.theme("a") for x in "bcdef"))

    def test_compose_and_duck(self):
        sheet = {"beats": [{"t_start": 0, "t_end": 6, "action": "Kaan koşar ve zıplar", "emotion": {"valence": .7, "arousal": .8}},
                           {"t_start": 6, "t_end": 12, "action": "sakin bekler", "emotion": {"valence": -.3, "arousal": .2}}]}
        a = mw.compose(sheet, "s1", speech=[(2, 4)])
        self.assertAlmostEqual(len(a) / mw.SR, 13, delta=1.1)
        self.assertGreater(max(abs(x) for x in a), 500)
        quiet = max(abs(x) for x in a[int(2.5 * mw.SR):int(3.5 * mw.SR)])
        loud = max(abs(x) for x in a[int(7 * mw.SR):int(9 * mw.SR)])
        self.assertGreater(loud + 1, 0)
        self.assertLessEqual(quiet, 20000)

    def test_run_writes_wav(self):
        d = tempfile.mkdtemp()
        json.dump({"beats": [{"t_start": 0, "t_end": 4, "action": "kapı çalar", "emotion": {"valence": .5, "arousal": .5}}]},
                  open(os.path.join(d, "beat_sheet.json"), "w"))
        m = mw.run(d, "s1")
        with wave.open(m["bed"]) as w:
            self.assertEqual(w.getframerate(), mw.SR)
        self.assertEqual(mw.mix(d, os.path.join(d, "yok.wav")), os.path.join(d, "yok.wav"))
