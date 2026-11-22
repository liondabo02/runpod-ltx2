import json, math, os, struct, sys, tempfile, unittest, wave
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import voice_worker as vw


def fake_tts(text, voice, rate, pitch, out):
    dur = max(0.4, len(text) * 0.06)
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(i / 20))) for i in range(int(16000 * dur))))


def fake_vis(wav, out):
    cues = [{"start": 0, "end": 0.2, "value": "X"}, {"start": 0.2, "end": 0.4, "value": "C"}]
    json.dump({"mouthCues": cues}, open(out, "w")); return cues


BIBLE = {"characters": [{"id": "pelin", "name": "Pelin", "age": 5, "role": "kız"},
                        {"id": "nine", "name": "Nine", "age": 70, "role": "kadın bekçi"},
                        {"id": "tosun", "name": "Tosun", "age": 4, "role": "kirpi", "voice_hint": "erkek çocuk"}]}


def sheet(dialogs):
    beats, t = [], 0
    for d in dialogs:
        beats.append({"t_start": t, "t_end": t + 8, "characters": ["pelin", "tosun"], "dialogue": d}); t += 8
    return {"beats": beats}


class T(unittest.TestCase):
    def run_w(self, dialogs):
        d = tempfile.mkdtemp()
        json.dump(sheet(dialogs), open(os.path.join(d, "beat_sheet.json"), "w"))
        return d, vw.run(d, BIBLE, fake_tts, fake_vis)

    def test_pass_and_manifest(self):
        d, m = self.run_w(["pelin: Bak! | tosun: Nerede?", "pelin: Burada"])
        self.assertEqual(m["status"], "PASSED"); self.assertEqual(m["lines"], 3)
        self.assertTrue(all(len(i["sha256"]) == 64 for i in m["items"]))
        self.assertTrue(os.path.exists(os.path.join(d, "voice_manifest.json")))

    def test_too_long_flagged(self):
        _, m = self.run_w(["pelin: " + "çok uzun bir cümle " * 12])
        self.assertEqual(m["status"], "NEEDS_REVISION")
        self.assertTrue(any("kısaltmalı" in p for p in m["problems"]))

    def test_unknown_speaker(self):
        _, m = self.run_w(["zzz: merhaba"])      # tanınmayan etiket: sahnedeki karaktere atanır, satır kaybolmaz
        self.assertEqual(m["lines"], 1)
        self.assertEqual(m["items"][0]["char"], "pelin")

    def test_unlabeled_lines_alternate(self):
        ch = {"pelin": {"name": "Pelin"}, "tosun": {"name": "Tosun"}}
        r = vw.parse_dialogue("Merhaba! | Nasılsın? | İyiyim.", ["pelin", "tosun"], ch)
        self.assertEqual([c for c, _ in r], ["pelin", "tosun", "pelin"])

    def test_voice_choice(self):
        self.assertEqual(vw.pick_voice(BIBLE["characters"][0])[0], vw.VOICE_F)
        self.assertEqual(vw.pick_voice(BIBLE["characters"][2])[0], vw.VOICE_M)
        hz = lambda c: int(vw.pick_voice(c)[2].replace("Hz", ""))
        self.assertTrue(-8 - 12 <= hz(BIBLE["characters"][1]) <= -8 + 12)
        self.assertTrue(35 - 12 <= hz(BIBLE["characters"][0]) <= 35 + 12)
        self.assertEqual(vw.pick_voice(BIBLE["characters"][0]), vw.pick_voice(BIBLE["characters"][0]))
        a, b = dict(BIBLE["characters"][0], id="x1"), dict(BIBLE["characters"][0], id="y2", name="Başka")
        self.assertNotEqual(vw.pick_voice(a)[1:], vw.pick_voice(b)[1:])

    def test_parse_names_inline(self):
        ch = {c["id"]: c for c in BIBLE["characters"]}
        r = vw.parse_dialogue("Pelin: Işık yanına! Tosun: Hadi koşalım. Nine: Hoş geldiniz!", "pelin", ch)
        self.assertEqual([c for c, _ in r], ["pelin", "tosun", "nine"]); self.assertEqual(r[0][1], "Işık yanına!")
        self.assertEqual(vw.parse_dialogue("merhaba", "pelin", ch), [("pelin", "merhaba")])

    def test_parse_default_speaker(self):
        self.assertEqual(vw.parse_dialogue("merhaba", "pelin"), [("pelin", "merhaba")])


if __name__ == "__main__":
    unittest.main()


class TestExpressive(unittest.TestCase):
    def test_punctuation_changes_prosody(self):
        import voice_worker as v
        a = v.expressive("Koşalım!", "+0%", "+0Hz", 0)
        b = v.expressive("Nerede acaba bu damla olabilir sence", "+0%", "+0Hz", 0)
        self.assertNotEqual(a, b)
        r, p = v.expressive("x", "+0%", "+0Hz", 3)
        self.assertTrue(r.endswith("%") and p.endswith("Hz"))
