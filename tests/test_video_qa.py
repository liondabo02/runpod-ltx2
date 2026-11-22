import os, subprocess, sys, tempfile, unittest, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import video_qa as vq

FF = shutil.which("ffmpeg")


@unittest.skipUnless(FF, "ffmpeg yok")
class T(unittest.TestCase):
    def mk(self, vsrc, audio, secs=6):
        d = tempfile.mkdtemp(); out = os.path.join(d, "a.mp4")
        cmd = [FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"{vsrc}size=1280x720:rate=12:duration={secs}"]
        cmd += (["-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}"] if audio else [])
        cmd += ["-pix_fmt", "yuv420p", out]
        subprocess.run(cmd, check=True); return out

    def test_good_video_passes(self):
        r = vq.check(self.mk("testsrc2=", True), 6); self.assertEqual(r["verdict"], "PASS", r["problems"])

    def test_blank_and_silent_fail(self):
        r = vq.check(self.mk("color=c=blue:", False), 6)
        self.assertEqual(r["verdict"], "NEEDS_REVISION"); self.assertTrue(any("ses" in p for p in r["problems"]))
        self.assertTrue(any("boş" in p or "değişmiyor" in p for p in r["problems"]))

    def test_wrong_duration(self):
        r = vq.check(self.mk("testsrc2=", True, 6), 20); self.assertTrue(any("süre" in p for p in r["problems"]))


if __name__ == "__main__":
    unittest.main()
