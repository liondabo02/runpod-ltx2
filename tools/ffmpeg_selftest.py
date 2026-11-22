"""ffmpeg bu makinede sahte video+ses üretebiliyor mu? Hata mesajını yazar (studio/reports/ffmpeg_selftest.json)."""
import json, os, shutil, subprocess, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ff = shutil.which("ffmpeg"); res = {"ffmpeg": ff}
d = tempfile.mkdtemp()
for name, extra in (("video_only", []), ("with_audio", ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"])):
    cmd = [ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=12:duration=2"] + extra + ["-pix_fmt", "yuv420p", "-strict", "-2", os.path.join(d, name + ".mp4")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    res[name] = {"rc": r.returncode, "err": (r.stderr or "")[-400:]}
os.makedirs(os.path.join(ROOT, "studio", "reports"), exist_ok=True)
json.dump(res, open(os.path.join(ROOT, "studio", "reports", "ffmpeg_selftest.json"), "w"), indent=1)
print(json.dumps(res))
