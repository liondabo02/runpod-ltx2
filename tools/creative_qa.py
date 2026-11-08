"""Teknik QA ile yaratıcı QA'yı ayıran ölçüm aracı (salt okunur).

Teknik katman ölçülür: konteyner/kodek/süre/fps/çözünürlük, kare sayısı,
donma, titreme (flicker), keskinlik, hareket enerjisi, parlaklık/doygunluk.
Yaratıcı katman **otomatik PASS edilmez**: yalnız ölçüm özeti ve insan onayı
notu üretilir. "Dosya açılıyor" teknik bir gerçektir; sanatsal kabul değildir.

Kullanım:
    python tools/creative_qa.py --video y.mp4 --out qa.json --frames-dir qa-frames
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FREEZE_PIXEL_DELTA = 8      # tek pikselde "değişti" sayılan fark (0-255)
FREEZE_PIXEL_RATIO = 0.002  # karenin %0,2'sinden azı değiştiyse "donmuş"
FLICKER_LUMA_DELTA = 6.0    # ardışık kare ortalama luma farkı eşiği


def _ffprobe(path: Path) -> dict:
    done = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if done.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {done.stderr.strip()[:400]}")
    return json.loads(done.stdout)


def _technical(probe: dict, path: Path) -> dict:
    video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = probe.get("format") or {}
    if video is None:
        return {"ok": False, "problems": ["video akışı yok"]}
    num, den = (video.get("avg_frame_rate") or "0/1").split("/")
    fps = round(float(num) / float(den), 3) if float(den or 1) else 0.0
    duration = float(fmt.get("duration") or video.get("duration") or 0)
    nb_frames = int(video.get("nb_frames") or 0)
    problems = []
    if duration <= 0.5:
        problems.append("süre <= 0.5 sn")
    if int(video.get("width") or 0) < 640 or int(video.get("height") or 0) < 360:
        problems.append("çözünürlük < 640x360")
    if fps <= 0:
        problems.append("fps okunamadı")
    if nb_frames and abs(nb_frames - round(duration * fps)) > max(3, 0.02 * nb_frames):
        problems.append("kare sayısı süre*fps ile uyuşmuyor")
    return {
        "ok": not problems,
        "problems": problems,
        "container": fmt.get("format_name"),
        "duration_seconds": round(duration, 3),
        "size_bytes": int(fmt.get("size") or path.stat().st_size),
        "video": {
            "codec": video.get("codec_name"), "profile": video.get("profile"),
            "width": video.get("width"), "height": video.get("height"),
            "fps": fps, "nb_frames": nb_frames,
            "bitrate": int(video.get("bit_rate") or 0) or None,
            "pix_fmt": video.get("pix_fmt"),
        },
        "audio": None if audio is None else {
            "codec": audio.get("codec_name"), "sample_rate": audio.get("sample_rate"),
            "channels": audio.get("channels"),
        },
    }


def _frames(path: Path, max_frames: int = 600):
    import cv2  # yerel bağımlılık; yoksa araç anlaşılır hata verir

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("video açılamadı (cv2)")
    previous = None
    diffs, changed, lumas, sharp = [], [], [], []
    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            lumas.append(float(gray.mean()))
            sharp.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            if previous is not None:
                delta = cv2.absdiff(gray, previous)
                diffs.append(float(delta.mean()))
                # Değişen piksel oranı: repo standardı (docs/STUDIO.md §3) ile aynı.
                changed.append(float((delta > FREEZE_PIXEL_DELTA).mean()))
            previous = gray
            frame_index += 1
            if frame_index >= max_frames:
                break
    finally:
        capture.release()
    return {"frames_scanned": frame_index, "diffs": diffs, "changed": changed,
            "lumas": lumas, "sharpness": sharp}


def _metrics(scan: dict, duration: float) -> dict:
    diffs = scan["diffs"] or [1.0]
    changed = scan["changed"] or [1.0]
    lumas = scan["lumas"] or [0.0]
    frozen = sum(1 for value in changed if value < FREEZE_PIXEL_RATIO)
    luma_deltas = [abs(b - a) for a, b in zip(lumas, lumas[1:])]
    motion = statistics.fmean(diffs)
    flicker = statistics.fmean(luma_deltas) if luma_deltas else 0.0
    return {
        "frames_scanned": scan["frames_scanned"],
        "motion_energy": round(motion, 3),
        "changed_pixel_ratio_mean": round(statistics.fmean(changed), 4),
        "freeze_ratio": round(frozen / max(1, len(changed)), 3),
        "freeze_verdict": "PASS" if frozen / max(1, len(changed)) <= 0.30 else "FAIL",
        "flicker_luma_delta": round(flicker, 3),
        "flicker_verdict": "PASS" if flicker <= FLICKER_LUMA_DELTA else "FAIL",
        "sharpness_laplacian": round(statistics.fmean(scan["sharpness"]), 2) if scan["sharpness"] else 0.0,
        "mean_luma": round(statistics.fmean(lumas), 2),
        "duration_vs_frames": round(scan["frames_scanned"] / duration, 2) if duration else 0.0,
    }


def _extract_frames(path: Path, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame-%03d.png")
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", "fps=1", pattern],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    if done.returncode != 0:
        return []
    return sorted(str(p) for p in out_dir.glob("frame-*.png"))


def evaluate(path: Path, *, out_dir: Path | None = None, scene_id: str = "") -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    probe = _ffprobe(path)
    technical = _technical(probe, path)
    report: dict = {
        "schema": "ahos.creative-qa.v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "video": str(path), "scene_id": scene_id,
        "technical": technical,
        "creative": {
            "status": "NOT_EVALUATED",
            "reason": "Yaratıcı kalite otomatik PASS edilmez; insan onayı gerekir.",
            "human_checks": [
                "karakter kimliği ve kıyafet sürekliliği",
                "doğal hareket ve ağırlık aktarımı",
                "ışık yönü/sıcaklığı ve gölge tutarlılığı",
                "kompozisyon ve sinematik his",
                "yüz/el/uzuv bozulmaları, titreme, zıplama",
                "genel estetik: profesyonel 3D çocuk animasyonu görünümü",
            ],
            "approver": "Harun",
        },
    }
    if technical.get("ok"):
        scan = _frames(path)
        report["motion"] = _metrics(scan, technical["duration_seconds"])
        if out_dir is not None:
            report["frames"] = _extract_frames(path, out_dir)
    else:
        report["motion"] = {"skipped": "teknik kontroller geçmedi"}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--frames-dir", default="")
    parser.add_argument("--scene", default="")
    args = parser.parse_args(argv)

    report = evaluate(Path(args.video),
                      out_dir=Path(args.frames_dir) if args.frames_dir else None,
                      scene_id=args.scene)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["technical"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
