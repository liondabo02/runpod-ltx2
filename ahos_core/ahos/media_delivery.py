"""AHOS-DELIVERY-001 — gerçek video üretim ve doğrulama hattı (medya).

Deterministik: PIL kareleri + edge-tts Türkçe ses + ffmpeg mux. GPU/model yok.
Üretilen dosya gerçek MP4'tür; kareler deterministik çizimdir (AI modeli iddiası yok).
Dosya/QA eksikse `verified=false`.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

FRAME_WIDTH, FRAME_HEIGHT, FPS = 1920, 1080, 24
SKY_TOP, SKY_BOTTOM = (38, 84, 156), (168, 214, 255)
GRASS, SUN = (74, 148, 84), (255, 226, 128)


def _gradient(width: int, height: int):
    import numpy as np
    from PIL import Image

    top = np.array(SKY_TOP, dtype=np.float32)
    bottom = np.array(SKY_BOTTOM, dtype=np.float32)
    rows = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    column = top[None, :] * (1 - rows) + bottom[None, :] * rows
    return Image.fromarray(
        np.repeat(column[:, None, :], width, axis=1).astype("uint8"), "RGB")


def render_frame(index: int, total: int, width: int = FRAME_WIDTH,
                 height: int = FRAME_HEIGHT):
    from PIL import ImageDraw, ImageEnhance

    t = index / max(1, total - 1)
    image = _gradient(width, height)
    draw = ImageDraw.Draw(image, "RGBA")
    s = width / 1920

    sun_x, sun_y = int(width * 0.84), int(height * 0.15)
    for radius, color in ((150, (74, 112, 168)), (112, (126, 160, 204)),
                          (80, (255, 236, 170))):
        rr = int(radius * s)
        draw.ellipse([sun_x - rr, sun_y - rr, sun_x + rr, sun_y + rr], fill=color)
    rr = int(62 * s)
    draw.ellipse([sun_x - rr, sun_y - rr, sun_x + rr, sun_y + rr], fill=SUN)

    drift = int(t * width * 0.05)
    for base_x, base_y in ((220, 190), (620, 130), (1180, 220)):
        cx, cy = int(base_x * s + drift), int(base_y * s)
        for dx, dy, r in ((-70, 10, 55), (0, -10, 75), (70, 14, 50), (30, 26, 60)):
            draw.ellipse([cx + int(dx * s) - int(r * s), cy + int(dy * s) - int(r * s),
                          cx + int(dx * s) + int(r * s), cy + int(dy * s) + int(r * s)],
                         fill=(255, 255, 255))

    draw.ellipse([-int(300 * s), int(height * 0.72), int(width * 0.55),
                  int(height * 1.15)], fill=(96, 152, 111))
    draw.ellipse([int(width * 0.40), int(height * 0.75), int(width * 1.30),
                  int(height * 1.20)], fill=(84, 140, 100))
    draw.rectangle([0, int(height * 0.80), width, height], fill=GRASS)
    for blade in range(0, width, int(46 * s)):
        bh = 26 + (blade * 7) % 30
        draw.line([blade, int(height * 0.80), blade + 8, int(height * 0.80) - bh],
                  fill=(58, 122, 70), width=max(2, int(3 * s)))

    def child(cx, cy, color, hair):
        r = int(58 * s)
        draw.ellipse([cx - r, cy - r * 3, cx + r, cy - r], fill=color)
        draw.ellipse([cx - r * 0.72, cy - r * 4.2, cx + r * 0.72, cy - r * 2.3],
                     fill=(250, 214, 184))
        draw.arc([cx - r * 0.8, cy - r * 4.6, cx + r * 0.8, cy - r * 3.0],
                 200, 340, fill=hair, width=max(3, int(8 * s)))
        draw.line([cx + r * 0.5, cy - r * 2.6, cx + r * 2.2, cy - r * 4.0],
                  fill=(90, 70, 60), width=max(2, int(4 * s)))

    child(int(width * 0.22), int(height * 0.90), (64, 132, 220), (94, 64, 44))
    child(int(width * 0.31), int(height * 0.91), (232, 120, 92), (60, 44, 34))

    # hikâye: 1) uçurtma uçar 2) kuyruk kopar 3) yeni kuyruk dikilir
    if t < 0.30:
        scene, tail_count, colors = 1, 6, [(255, 214, 90)]
        kx, ky = int(width * 0.60), int(height * 0.30)
    elif t < 0.62:
        scene = 2
        progress = (t - 0.30) / 0.32
        tail_count = max(2, 6 - int(progress * 5))
        colors = [(255, 214, 90)]
        kx = int(width * (0.60 + math.sin(progress * 22) * 0.012))
        ky = int(height * (0.30 + progress * 0.05))
    else:
        scene, tail_count = 3, 7
        colors = [(230, 72, 96), (255, 214, 90), (64, 132, 220), (110, 190, 120)]
        kx, ky = int(width * 0.62), int(height * 0.22)
    bob = math.sin(t * math.tau * 1.4) * 26 * s
    ky = ky + int(bob)
    w, h = int(92 * s), int(120 * s)
    draw.polygon([(kx, ky - h), (kx + w, ky), (kx, ky + h), (kx - w, ky)],
                 fill=(230, 72, 96))
    draw.line([(kx, ky - h), (kx, ky + h)], fill=(250, 250, 250),
              width=max(2, int(4 * s)))
    draw.line([(kx - w, ky), (kx + w, ky)], fill=(250, 250, 250),
              width=max(2, int(4 * s)))
    tail_start = (kx, ky + h)
    for segment in range(tail_count):
        phase = t * math.tau * 2 + segment * 0.9
        tx = kx + int(math.sin(phase) * 26 * s)
        ty = ky + h + int((segment + 1) * 34 * s)
        color = colors[segment % len(colors)]
        draw.line([tail_start, (tx, ty)], fill=color, width=max(2, int(5 * s)))
        draw.ellipse([tx - 7, ty - 7, tx + 7, ty + 7], fill=color)
        tail_start = (tx, ty)
    if scene == 2:
        # kopan kuyruk parçaları yere doğru süzülür
        progress = (t - 0.30) / 0.32
        for piece in range(4):
            px = int(width * (0.52 + piece * 0.05))
            py = int(height * (0.55 + progress * 0.30) + piece * 14 * s)
            draw.rectangle([px, py, px + int(18 * s), py + int(12 * s)],
                           fill=(255, 214, 90))
    if scene == 3:
        # yeni kuyruk için renkli kumaş parçaları
        for index, color in enumerate(colors):
            px = int(width * 0.20 + index * 34 * s)
            py = int(height * 0.93)
            draw.rectangle([px, py, px + int(26 * s), py + int(16 * s)], fill=color)

    if t < 0.08:
        image = ImageEnhance.Brightness(image).enhance(0.55 + t / 0.08 * 0.45)
    elif t > 0.92:
        image = ImageEnhance.Brightness(image).enhance(max(0.4, 1 - (t - 0.92) / 0.08 * 0.6))
    return image


def render_frames(out_dir, *, seconds=5.0, fps=FPS, width=FRAME_WIDTH,
                  height=FRAME_HEIGHT) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    total = max(1, int(round(seconds * fps)))
    existing = sorted(out.glob("frame_*.png"))
    if len(existing) >= total:  # aynı parametrelerle yeniden üretimde kareleri koru
        return {"frames": total, "fps": fps, "width": width, "height": height,
                "seconds": round(total / fps, 3), "dir": str(out), "cached": True}
    for index in range(total):
        render_frame(index, total, width, height).save(out / f"frame_{index:05d}.png")
    return {"frames": total, "fps": fps, "width": width, "height": height,
            "seconds": round(total / fps, 3), "dir": str(out)}


def synthesize(text: str, out_mp3, voice: str = "tr-TR-EmelNeural") -> str:
    import asyncio
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    import edge_tts

    async def run() -> None:
        await edge_tts.Communicate(text, voice).save(str(out_mp3))

    asyncio.run(run())
    return str(out_mp3)


def _run(command: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-300:]}")
    return proc


def build_audio(narration_mp3, out_wav, *, seconds: float, sample_rate: int = 48000) -> str:
    """Anlatımı 48k stereo WAV'a çözer; sessizliği doldurur, hafif rüzgâr ekler.

    ffmpeg filtrelerine bağımlı değildir (statik build'lerde eksik olabiliyor):
    PCM çözme ffmpeg ile, karışım numpy ile yapılır.
    """

    import wave

    import numpy as np

    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(narration_mp3),
                           "-f", "s16le", "-ac", "2", "-ar", str(sample_rate), "-"],
                          capture_output=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"narration decode failed: {proc.stderr[-200:]}")
    audio = np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768.0
    target = int(round(seconds * sample_rate)) * 2
    if audio.size >= target:
        audio = audio[:target]
    else:
        audio = np.pad(audio, (0, target - audio.size))
    samples = target // 2
    rng = np.random.default_rng(7)
    wind = rng.normal(0.0, 0.012, samples).astype(np.float32)
    # tek kutuplu alçak geçiren: yumuşak rüzgâr
    for index in range(1, samples):
        wind[index] = wind[index - 1] * 0.985 + wind[index] * 0.015
    wind = np.repeat(wind[:, None], 2, axis=1).reshape(-1)
    mixed = audio + wind
    fade = int(0.35 * sample_rate)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        mixed[: fade * 2] *= np.repeat(ramp, 2)
        tail = min(fade, samples)
        mixed[-tail * 2:] *= np.repeat(np.linspace(1.0, 0.0, tail, dtype=np.float32), 2)
    pcm = (np.clip(mixed, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(out_wav), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return str(out_wav)


def mux(frames_dir, audio, out_mp4, *, fps: int = FPS, seconds: float = 5.0) -> str:
    _run(["ffmpeg", "-y", "-framerate", str(fps),
          "-i", str(Path(frames_dir) / "frame_%05d.png"), "-i", str(audio),
          "-c:v", "libx264", "-preset", "medium", "-crf", "20",
          "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-strict", "-2",
          "-b:a", "128k",
          "-shortest", "-t", str(seconds), "-movflags", "+faststart", str(out_mp4)])
    return str(out_mp4)


def probe(path) -> dict:
    return json.loads(_run(["ffprobe", "-v", "error", "-print_format", "json",
                             "-show_format", "-show_streams", str(path)]).stdout)


def sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frame_stats(path, samples: int = 6) -> dict:
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(str(path))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    values = []
    if total > 0:
        for position in [int(total * (i + 0.5) / samples) for i in range(samples)]:
            capture.set(cv2.CAP_PROP_POS_FRAMES, position)
            ok, frame = capture.read()
            if ok and frame is not None:
                values.append(float(np.std(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))))
    capture.release()
    return {"frames": total, "min_std": round(min(values), 2) if values else 0.0,
            "mean_std": round(sum(values) / len(values), 2) if values else 0.0,
            "sampled": len(values)}


def audio_stats(path) -> dict:
    """Ses akışını PCM'e çözüp RMS'i numpy ile ölçer (ffmpeg filtresi gerekmez)."""

    import numpy as np

    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                           "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                          capture_output=True, timeout=300)
    if proc.returncode != 0 or not proc.stdout:
        return {"rms_db": None, "exit": proc.returncode}
    data = np.frombuffer(proc.stdout, dtype="<i2").astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0
    db = round(20 * math.log10(rms), 2) if rms > 1e-9 else None
    return {"rms_db": db, "samples": int(data.size), "exit": proc.returncode}


def verify_video(path, *, seconds: float, fps: int, width: int, height: int) -> dict:
    target = Path(path)
    checks = {"exists": target.is_file() and target.stat().st_size > 0}
    if not checks["exists"]:
        return {"ok": False, "checks": checks}
    info = probe(target)
    streams = info.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    checks["video_stream"] = video is not None
    checks["audio_stream"] = audio is not None
    duration = float((info.get("format") or {}).get("duration") or 0.0)
    checks["duration_ok"] = abs(duration - seconds) <= 0.35
    checks["resolution_ok"] = bool(video) and int(video.get("width", 0)) == width and int(
        video.get("height", 0)) == height
    rate = str((video or {}).get("avg_frame_rate") or "0/1")
    try:
        num, den = rate.split("/")
        actual_fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        actual_fps = 0.0
    checks["fps_ok"] = abs(actual_fps - fps) <= 0.1
    stats = frame_stats(target)
    checks["frames_ok"] = stats["frames"] >= int(seconds * fps * 0.8)
    checks["not_blank"] = stats["min_std"] >= 8.0
    sound = audio_stats(target)
    checks["audio_not_silent"] = bool(sound["rms_db"] is not None and sound["rms_db"] > -42.0)
    checks.update({"sha256": sha256(target), "bytes": target.stat().st_size,
                   "duration": round(duration, 3), "fps": round(actual_fps, 3),
                   "frame_stats": stats, "rms_db": sound["rms_db"]})
    boolean = [value for key, value in checks.items()
               if isinstance(value, bool)]
    return {"ok": all(boolean), "checks": checks}


def write_manifest(path, payload: dict) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def srt(rows: list[tuple[float, float, str]]) -> str:
    def stamp(value: float) -> str:
        millis = int(round(value * 1000))
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        secs, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    lines = []
    for index, (start, end, text) in enumerate(rows, 1):
        lines += [str(index), f"{stamp(start)} --> {stamp(end)}", text, ""]
    return "\n".join(lines)
