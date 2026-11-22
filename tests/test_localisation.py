import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import localisation_worker as lw


class T(unittest.TestCase):
    def test_translate_fit_and_voice(self):
        d = tempfile.mkdtemp()
        beats = [{"t_start": 0, "t_end": 10, "characters": ["a", "b"], "dialogue": "a: Burada mı? | b: Evet, burada!", "action": "x", "location": "l"}]
        json.dump({"beats": beats}, open(os.path.join(d, "beat_sheet.json"), "w"))
        bible = {"characters": [{"id": "a", "name": "Ali", "age": 5, "role": "kız"}, {"id": "b", "name": "Bo", "age": 40}]}
        calls = []

        def llm(sys_, user, temperature=0.4, need=None, tries=5):
            data = json.loads(user.split("\n", 2)[2])
            calls.append(len(data))
            # ilk turda bir satır çok uzun dönsün, kısaltma turu düzeltsin
            if len(calls) == 1:
                return {"lines": [{"i": data[0]["i"], "text": "Is it here? " * 20}, {"i": data[1]["i"], "text": "Yes, it is!"}]}
            return {"lines": [{"i": data[0]["i"], "text": "Here?"}]}
        seen = {}

        def tts(text, voice, rate, pitch, out):
            import wave
            seen[out] = voice
            with wave.open(out, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 16000)

        def vis(wav, vj):
            json.dump({"mouthCues": [{"start": 0, "end": 0.5, "value": "C"}]}, open(vj, "w")); return [1]
        r = lw.run(d, bible, ["en", "de"], llm=llm, tts=tts, visemes=vis)
        self.assertEqual([x["lang"] for x in r], ["en", "de"])
        sheet = json.load(open(os.path.join(d, "lang", "en", "beat_sheet.json"), encoding="utf-8"))
        self.assertIn("a: Here?", sheet["beats"][0]["dialogue"])
        self.assertTrue(any(v.startswith("en-US") for v in seen.values()))
        self.assertTrue(any(v.startswith("de-DE") for v in seen.values()))
        self.assertEqual(r[0]["untranslated"], [])
        self.assertTrue(os.path.exists(os.path.join(d, "lang", "en", "voice_manifest.json")))


if __name__ == "__main__":
    unittest.main()


class TMis(unittest.TestCase):
    def test_wrong_ids_and_dropped_lines(self):
        lines = [{"char": "a", "text": "x%d" % i} for i in range(10)]
        state = {"n": 0}

        def llm(s, u, temperature=0.4, need=None, tries=5):
            data = json.loads(u.split("\n", 2)[2]); state["n"] += 1
            if state["n"] == 1:      # yanlış numaralı ama tam
                return {"lines": [{"i": 100 + k, "text": "t%d" % k} for k in range(len(data))]}
            if state["n"] == 2:      # eksik satır
                return {"lines": [{"i": 0, "text": "t0"}]}
            return {"lines": [{"i": 0, "text": "ok"}]}
        r = lw.translate(lines, "English", [50] * 10, llm)
        self.assertEqual(sorted(r), list(range(10)))


class TKmr(unittest.TestCase):
    def test_text_only_language(self):
        import tempfile, json as _j
        d = tempfile.mkdtemp()
        _j.dump({"beats": [{"t_start": 0, "t_end": 6, "dialogue": "a: Merhaba"}]}, open(os.path.join(d, "beat_sheet.json"), "w"))
        bible = {"characters": [{"id": "a", "name": "A"}]}
        called = []
        rep = lw.build_lang_dir(d, bible, "kmr", {"name": "Kurdî", "tts": "none"}, llm=lambda s, u: _j.dumps({"items": [{"i": 0, "text": "Silav"}]}),
                                tts=lambda *a, **k: called.append(1))
        self.assertEqual(called, [])
        self.assertIn(rep["status"], ("TEXT_ONLY", "NEEDS_REVISION"))
