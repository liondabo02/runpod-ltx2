"""Çizgi film teslim kabulü: "oynuyor mu" değil, "profesyonel teslim mi" sorusu.

Bu ortamdaki ffmpeg eski (2.x): `freezedetect`/`-hide_banner` yok. Bu yüzden
hareket ve sahne geçişi **kare örnekleyerek** ölçülür (ffmpeg ile 4 fps PNG,
Pillow ile fark). Böylece denetim ffmpeg sürümüne bağımlı olmaz.

Ölçülenler:
1. Oynatılabilirlik: ffprobe süre + video akışı + çözünürlük.
2. Süre: beyan edilen süre ile gerçek süre ±%5.
3. Hareket: ≥0,5 sn boyunca fark yoksa "donmuş" sayılır (slayt teslimi) → ret.
4. Sahne geçişi: fark sıçraması sayısı ≥ sahne-1.
5. Altyazı: .srt satır sayısı.
6. Ses: beyan varsa zorunlu; yoksa "ses yok" notu ve skor düşer.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SAMPLE_FPS = 4
MOTION_MIN_RATIO = 0.002   # değişen piksel oranı; altı "hareketsiz"
CUT_RATIO = 0.25           # sahne geçişi sayılan değişim oranı
FREEZE_MIN_SAMPLES = 3      # 0.75 sn (4 fps)


def _run(command: list[str], timeout: float = 600.0) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _probe(video: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe bulunamadı")
    result = _run([
        ffprobe, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(video),
    ])
    if result.returncode != 0:
        raise RuntimeError("ffprobe hatası: " + (result.stderr or "")[-200:])
    return json.loads(result.stdout or "{}")


def motion_profile(video: Path, *, fps: int = SAMPLE_FPS) -> list[float]:
    """Ardışık örneklenmiş kareler arasında DEĞİŞEN piksel oranı (0-1).

    Ortalama parlaklık farkı yerine değişen piksel oranı kullanılır: küçük ama
    gerçek bir karakter hareketi, tüm kareye yayılan hafif bir gürültüden daha
    anlamlıdır. Slayt teslimi ~0 verir.
    """

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg bulunamadı")

    try:
        from PIL import Image, ImageChops
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Pillow gerekli: " + type(exc).__name__)

    with tempfile.TemporaryDirectory() as tmp:
        result = _run([
            ffmpeg, "-y", "-loglevel", "error", "-i", str(video),
            "-vf", f"fps={fps},scale=320:-1", str(Path(tmp) / "f_%04d.png"),
        ])
        if result.returncode != 0:
            raise RuntimeError("kare örnekleme hatası: " + (result.stderr or "")[-200:])
        frames = sorted(Path(tmp).glob("f_*.png"))
        if len(frames) < 2:
            return []
        ratios: list[float] = []
        previous = Image.open(frames[0]).convert("RGB")
        for path in frames[1:]:
            current = Image.open(path).convert("RGB")
            diff = ImageChops.difference(previous, current).convert("L")
            histogram = diff.histogram()
            moved = sum(histogram[9:])          # 8'den büyük fark = hareket
            total = diff.width * diff.height
            ratios.append(moved / total if total else 0.0)
            previous = current
        return ratios


def _runs(values: list[float], limit: float, minimum: int) -> int:
    runs = 0
    streak = 0
    for value in values:
        if value < limit:
            streak += 1
        else:
            if streak >= minimum:
                runs += 1
            streak = 0
    if streak >= minimum:
        runs += 1
    return runs


def _count_srt(path: Path) -> int:
    if not path.is_file():
        return 0
    body = path.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r"^\d+$", body, flags=re.MULTILINE))


def verify_episode(
    video: str | Path,
    *,
    expected_scenes: int,
    expected_duration: float | None = None,
    subtitles: str | Path | None = None,
    expects_audio: bool = False,
    expected_cuts: int | None = None,
    duration_tolerance: float = 0.05,
) -> dict:
    video_path = Path(video).resolve()
    problems: list[str] = []
    notes: list[str] = []

    if not video_path.is_file() or video_path.stat().st_size < 1024:
        return {"passed": False, "problems": ["video yok veya boş"], "measurements": {}}

    info = _probe(video_path)
    streams = info.get("streams") or []
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float((info.get("format") or {}).get("duration") or 0.0)

    if not video_streams:
        problems.append("video akışı yok")
        resolution = None
    else:
        resolution = [int(video_streams[0].get("width") or 0), int(video_streams[0].get("height") or 0)]
        if resolution[0] < 640 or resolution[1] < 360:
            problems.append(f"çözünürlük düşük: {resolution[0]}x{resolution[1]}")
    if duration <= 0.5:
        problems.append(f"süre çok kısa: {duration:.2f}s")

    if expected_duration:
        delta = abs(duration - expected_duration) / max(expected_duration, 1e-6)
        if delta > duration_tolerance:
            problems.append(f"süre sapması: {duration:.2f}s (beklenen {expected_duration:.2f}s)")

    try:
        diffs = motion_profile(video_path)
    except RuntimeError as exc:
        diffs = []
        problems.append(f"hareket ölçülemedi: {exc}")

    freeze_runs = _runs(diffs, MOTION_MIN_RATIO, FREEZE_MIN_SAMPLES) if diffs else 0
    cuts = sum(1 for value in diffs if value >= CUT_RATIO)

    if diffs and freeze_runs:
        problems.append(f"hareketsiz bölüm(ler): {freeze_runs} (slayt teslimi)")
    # Kesme sayısı, senaryonun görsel planına göre beyan edilir: aynı mekânda
    # geçen ardışık sahnelerde kesme olmaması doğaldır.
    required_cuts = expected_cuts if expected_cuts is not None else max(0, int(expected_scenes) - 1)
    if diffs and required_cuts and cuts < required_cuts:
        problems.append(f"sahne geçişi az: {cuts} (beklenen ≥{required_cuts})")

    if expects_audio and not audio_streams:
        problems.append("ses akışı yok")
    elif not expects_audio and not audio_streams:
        notes.append("ses yok: teslim profesyonel seslendirme içermiyor")

    srt_count = _count_srt(Path(subtitles)) if subtitles else 0
    if subtitles and srt_count == 0:
        problems.append("altyazı yok veya boş")

    score = max(0.0, min(100.0, 100.0 - 25 * len(problems) - (10 if notes else 0)))
    passed = not problems and score >= 70

    return {
        "passed": passed,
        "score": score,
        "problems": problems,
        "notes": notes,
        "measurements": {
            "duration_seconds": round(duration, 2),
            "video_streams": len(video_streams),
            "audio_streams": len(audio_streams),
            "resolution": resolution,
            "motion_samples": len(diffs),
            "freeze_runs": freeze_runs,
            "scene_cuts": cuts,
            "subtitle_cues": srt_count,
        },
        "scope": "codec/akış/süre/hareket/sahne/altyazı; içerik ve sanatsal kalite doğrulanmaz",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="çizgi film teslim denetimi")
    parser.add_argument("video")
    parser.add_argument("--scenes", type=int, required=True)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--subtitles", default=None)
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = verify_episode(
        args.video,
        expected_scenes=args.scenes,
        expected_duration=args.duration,
        subtitles=args.subtitles,
        expects_audio=args.audio,
    )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
