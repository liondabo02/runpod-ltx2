import json, math, os, struct, sys, tempfile, unittest, wave
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import animatic_worker as aw


def mk_wav(path, dur=1.0):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(i / 15))) for i in range(int(16000 * dur))))


class T(unittest.TestCase):
    def test_animatic_end_to_end(self):
        d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "audio"))
        beats = [{"t_start": 0, "t_end": 6, "location": "bahce", "light_time": "sabah", "characters": ["a"],
                  "action": "Pelin ğüşiöç Türkçe karakter denemesi yapıyor", "dialogue": "a: Merhaba!", "camera": "orta", "sound": "müzik"},
                 {"t_start": 6, "t_end": 12, "location": "cati", "characters": ["a", "b"], "action": "ikinci", "camera": "yakın", "sound": "rüzgâr"}]
        json.dump({"title": "Deneme", "beats": beats}, open(os.path.join(d, "beat_sheet.json"), "w", encoding="utf-8"), ensure_ascii=False)
        mk_wav(os.path.join(d, "audio", "x.wav"))
        json.dump({"items": [{"beat": 0, "char": "a", "wav": "audio/x.wav"}]}, open(os.path.join(d, "voice_manifest.json"), "w"))
        m = aw.run(d)
        self.assertEqual(m["status"], "PASSED"); self.assertEqual(m["resolution"], (1280, 720))
        self.assertAlmostEqual(m["duration_s"], 12, delta=1.0)
        self.assertEqual(len(m["artifact"]["sha256"]), 64)

    def test_works_without_audio(self):
        d = tempfile.mkdtemp()
        beats = [{"t_start": 0, "t_end": 6, "location": "x", "characters": [], "action": "a", "camera": "c", "sound": "s"}]
        json.dump({"beats": beats}, open(os.path.join(d, "beat_sheet.json"), "w"))
        m = aw.run(d); self.assertEqual(m["voiced_lines"], 0); self.assertEqual(m["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()
