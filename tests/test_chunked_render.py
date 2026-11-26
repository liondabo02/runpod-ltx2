"""Parça parça üretim: süre doğrulama, devam (yeniden üretmeme), yalnız kendi karelerini silme (disk yetmezse), başarısızlıkta durma."""
import os, subprocess, shutil, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import render_worker as rw

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg yok")


def _mk_clip(path, seconds):
    subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=12", "-t", str(seconds), "-pix_fmt", "yuv420p", path], check=True)


def _runner_factory(calls, fail_at=None, bad_len=None):
    def runner(ep, bible, a, b, sd, engine, samples):
        calls.append((a, b))
        if fail_at is not None and a == fail_at:
            return {"status": "BLOCKED", "error": "DISK_YETERSIZ", "problems": ["x"]}
        rdir = os.path.join(ep, "render"); fdir = os.path.join(rdir, "frames"); os.makedirs(fdir, exist_ok=True)
        for i in range(int(a * 12), int(b * 12) + 1):
            open(os.path.join(fdir, f"f{i:05d}.png"), "wb").write(b"x" * 1000)
        clip = os.path.join(rdir, f"clip_{int(a)}_{int(b)}.mp4"); _mk_clip(clip, bad_len if bad_len else b - a)
        return {"status": "PASSED", "clip": clip}
    return runner


def test_chunks_join_and_reuse_verified_parts(tmp_path):
    ep = str(tmp_path); calls = []
    m = rw.run_chunked(ep, {}, 0, 6, ep, chunk_s=2, runner=_runner_factory(calls), free_bytes=10**12)
    assert m["status"] == "PASSED" and abs(m["seconds"] - 6) < 0.5 and len(calls) == 3 and not m["purge_mode"]
    assert os.path.exists(os.path.join(ep, "render", "frames", "f00000.png"))       # yer yetiyor -> hiçbir şey silinmez
    calls.clear()
    m2 = rw.run_chunked(ep, {}, 0, 6, ep, chunk_s=2, runner=_runner_factory(calls), free_bytes=10**12)
    assert calls == [] and all(c["status"] == "REUSED" for c in m2["chunks"])      # devam: doğrulanmış parça yeniden üretilmez


def test_low_disk_purges_only_own_encoded_chunk_frames(tmp_path):
    ep = str(tmp_path); calls = []
    foreign = os.path.join(ep, "render", "frames"); os.makedirs(foreign, exist_ok=True)
    keep = os.path.join(ep, "render", "baska_isin_dosyasi.txt"); open(keep, "w").write("dokunma")
    m = rw.run_chunked(ep, {}, 0, 4, ep, chunk_s=2, runner=_runner_factory(calls), free_bytes=1000)
    assert m["status"] == "PASSED" and m["purge_mode"] and all(c["freed_mb"] >= 0 for c in m["chunks"])
    assert not os.path.exists(os.path.join(foreign, "f00000.png")) and os.path.exists(keep)


def test_length_mismatch_and_failure_stop_the_pipeline(tmp_path):
    ep = str(tmp_path)
    m = rw.run_chunked(ep, {}, 0, 4, ep, chunk_s=2, runner=_runner_factory([], bad_len=0.5), free_bytes=10**12)
    assert m["status"] == "BLOCKED" and m["error"] == "CHUNK_SURE_UYUSMAZ"          # eksik/kısa klip başarılı görünmez
    ep2 = str(tmp_path / "b"); os.makedirs(ep2)
    m2 = rw.run_chunked(ep2, {}, 0, 4, ep2, chunk_s=2, runner=_runner_factory([], fail_at=2), free_bytes=10**12)
    assert m2["status"] == "BLOCKED" and m2["error"] == "DISK_YETERSIZ" and m2["parts_done"][0]["status"] == "DONE"
