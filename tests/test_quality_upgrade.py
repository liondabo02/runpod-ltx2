# -*- coding: utf-8 -*-
import json, os, sys, tempfile, unittest, wave
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import numpy as np  # noqa: E402


class TQuality(unittest.TestCase):
    def test_polish_trims_silence(self):
        import audio_polish as ap
        sr = 16000; t = np.arange(int(0.4 * sr)) / sr
        x = np.concatenate([np.zeros(int(.25 * sr)), 0.2 * np.sin(2 * np.pi * 200 * t), np.zeros(sr)])
        p = tempfile.mktemp(suffix=".wav")
        with wave.open(p, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((x * 32767).astype("<i2").tobytes())
        r = ap.polish_wav(p)
        with wave.open(p) as w:
            dur = w.getnframes() / sr
        os.remove(p)
        self.assertTrue(r["trimmed"]); self.assertLess(dur, 0.8)

    def test_score_engine(self):
        import score_engine as se
        sheet = {"beats": [{"t_start": i * 5.0, "t_end": (i + 1) * 5.0, "scene_id": "A" if i < 2 else "B", "emotion": {"arousal": 0.3 + 0.1 * i, "valence": 0.6}, "action": ""} for i in range(4)]}
        x = se.compose(sheet, "test-dizi", [(1, 2)])
        st = se.stats(x)
        self.assertAlmostEqual(st["seconds"], 21.0, delta=1.1); self.assertGreater(st["rms"], 0.005); self.assertLessEqual(st["peak"], 1.0)
        self.assertEqual(se.theme("test-dizi")["melody"], se.theme("test-dizi")["melody"])      # tema dizi boyunca sabit
        self.assertNotEqual(se.theme("a-dizi")["melody"], se.theme("b-dizi")["melody"])

    def test_letter_window_catches_short_visemes(self):
        import render2d as r2
        cues = [[0.0, 0.10, 0.1, "X"], [0.10, 0.17, 0.5, "B"], [0.17, 0.30, 0.1, "X"]]
        self.assertEqual(r2.letter_window(cues, 0.08, 1 / 12.0), "B")

    def test_icons_rules(self):
        import fx_layer
        self.assertIn("heart", fx_layer.kinds_for("Aden annesine sarılır"))
        self.assertIn("zzz", fx_layer.kinds_for("bebek uykuda"))

    def test_enrich_keeps_dialogue(self):
        import script_enrich as se
        sheet = {"beats": [{"t_start": 0, "t_end": 6, "shot_id": "s1", "scene_id": "A", "characters": ["aden", "esra"], "action": "Aden konuşur.", "dialogue": "aden: Merhaba anne!", "sound": "ortam"}]}
        bible = {"characters": [{"id": "aden", "name": "Aden"}, {"id": "esra", "name": "Esra"}]}
        out, rep = se.enrich(sheet, bible, use_llm=False)
        self.assertEqual(out["beats"][0]["dialogue"], "aden: Merhaba anne!")
        self.assertEqual(out["beats"][0]["t_end"], 6); self.assertIn("EK:", out["beats"][0]["action"])

    def test_script_parse(self):
        import script_enrich as se
        r = se._parse("ÇEKİM s1 | TEPKİ: Esra güler | ARKA: kuş uçar | ŞAKA: - | SES: adım", {"s1"}, None)
        self.assertEqual(r["s1"]["TEPKİ"], "Esra güler"); self.assertNotIn("ŞAKA", r["s1"])

    def test_json_repair(self):
        import writers_room as wr
        self.assertEqual(wr.extract_json('{"a":[{"x":1}\n{"x":2},],"b":"k"\n"c":3}')["c"], 3)

    def test_standards_face_distance(self):
        import studio_standards_check as sc
        d = tempfile.mkdtemp()
        for cid, shp in (("a", "round"), ("b", "round")):
            json.dump({"eye_shape": shp}, open(os.path.join(d, cid + ".spec.json"), "w"))
        r = sc.face_distinctness({"characters": [{"id": "a"}, {"id": "b"}]}, d)
        self.assertEqual(r["min_pair_distance"], 0)


if __name__ == "__main__":
    unittest.main()
