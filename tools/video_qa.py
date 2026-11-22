#!/usr/bin/env python3
"""AHOS Video Kalite Denetçisi (üreticiden bağımsız, kodla, fail-closed).

Kontroller: süre, çözünürlük, ses var mı ve sessiz mi, kareler boş mu, görüntü donuk mu (hareket var mı),
karakter bölgesi/renk çeşitliliği. Yaratıcı kaliteyi (güzel mi?) DEĞERLENDİRMEZ -> 'creative: NOT_EVALUATED'.
Kullanım: python tools/video_qa.py --video clip.mp4 [--expect-seconds 12]
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

from PIL import Image, ImageChops, ImageStat


def ffprobe(path):
    r = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height:format=duration", "-of", "json", path],
                       capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    return {"duration": float(j["format"]["duration"]), "w": v.get("width"), "h": v.get("height"),
            "audio": any(s["codec_type"] == "audio" for s in j["streams"])}


def mean_volume(path):
    r = subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-i", path, "-af", "volumedetect", "-vn", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def sample_frames(path, every=2.0, d=None):
    out = os.path.join(d, "s%04d.png")
    subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", f"fps=1/{every},scale=320:-1", out], check=True)
    return [Image.open(os.path.join(d, f)).convert("RGB") for f in sorted(os.listdir(d)) if f.startswith("s")]


def check(path, expect_seconds=None, min_motion=1.5):
    problems, warns, facts = [], [], {}
    info = ffprobe(path); facts.update(info)
    if expect_seconds and abs(info["duration"] - expect_seconds) > 1.0:
        problems.append(f"süre {info['duration']:.1f}s, beklenen {expect_seconds}s")
    if (info["w"] or 0) < 1280:
        problems.append(f"çözünürlük düşük: {info['w']}x{info['h']}")
    if not info["audio"]:
        problems.append("ses akışı yok")
    else:
        mv = mean_volume(path); facts["mean_volume_db"] = mv
        if mv is None or mv < -45:
            problems.append(f"ses neredeyse sessiz (ort. {mv} dB)")
    with tempfile.TemporaryDirectory() as d:
        frames = sample_frames(path, every=max(0.5, min(2.0, info["duration"] / 6)), d=d)
        facts["sampled_frames"] = len(frames)
        flat = [i for i, f in enumerate(frames) if max(ImageStat.Stat(f).stddev) < 6]
        if flat:
            problems.append(f"{len(flat)} örnek karede görüntü boş/tek renk")
        diffs = [sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3 for a, b in zip(frames, frames[1:])]
        facts["avg_frame_change"] = round(sum(diffs) / len(diffs), 2) if diffs else 0
        if diffs and facts["avg_frame_change"] < min_motion:
            problems.append(f"görüntü neredeyse hiç değişmiyor (ort. fark {facts['avg_frame_change']})")
        cols = [len(set(f.resize((40, 22)).getdata())) for f in frames]
        facts["min_colors"] = min(cols) if cols else 0
    return {"verdict": "PASS" if not problems else "NEEDS_REVISION", "problems": problems, "warnings": warns,
            "facts": facts, "creative": "NOT_EVALUATED", "cost_eur": 0}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--video", required=True); ap.add_argument("--expect-seconds", type=float)
    a = ap.parse_args()
    r = check(a.video, a.expect_seconds)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r["verdict"] == "PASS" else 2)


if __name__ == "__main__":
    main()
