"""2D çizgi film üretimi: karakter rig'i + sahne + montaj.

Tasarım kararı (tek adam):
- Sahne görselleri kodla çizilir (Pillow). Böylece her kare deterministik,
  karakterler sahne sahne AYNI (renk, oran, isim) kalır.
- Hareket gerçektir: gövde salınımı, göz kırpma, ağız hareketi (konuşma
  zamanlamasına bağlı), kol jesti, kamera kaydırma. Slayt değildir.
- Ses: varsa piper ile üretilir; yoksa sessiz + altyazı. Ses yoksa QA bunu
  "ses yok" olarak işaretler — sahte teslim sayılmaz.

Çıktı: frames/ (PNG), episode.mp4, episode.srt, episode.json (kanıt).
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1280, 720
FPS = 24

PALETTE = {
    "aden": {"skin": (245, 205, 170), "hair": (70, 45, 30), "shirt": (40, 110, 200), "pants": (40, 50, 70)},
    "kaan": {"skin": (232, 190, 150), "hair": (25, 25, 30), "shirt": (220, 90, 70), "pants": (60, 60, 90)},
    "anne": {"skin": (240, 200, 165), "hair": (120, 60, 30), "shirt": (230, 170, 60), "pants": (80, 60, 90)},
}


@dataclass
class Line:
    scene_id: str
    speaker: str
    text: str
    seconds: float


@dataclass
class Scene:
    scene_id: str
    setting: str
    background: str = "day"
    characters: list[str] = field(default_factory=lambda: ["aden", "kaan"])
    lines: list[Line] = field(default_factory=list)
    seconds: float | None = None

    def duration(self) -> float:
        return float(self.seconds if self.seconds is not None else sum(line.seconds for line in self.lines) or 3.0)


@dataclass
class Episode:
    title: str
    scenes: list[Scene]
    language: str = "tr"

    def duration(self) -> float:
        return sum(scene.duration() for scene in self.scenes)


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _background(draw: ImageDraw.ImageDraw, kind: str, t: float, shift: float) -> None:
    if kind == "night":
        for y in range(HEIGHT):
            k = y / HEIGHT
            draw.line([(0, y), (WIDTH, y)], fill=(int(15 + 15 * k), int(20 + 25 * k), int(55 + 35 * k)))
        draw.ellipse([1000, 80, 1120, 200], fill=(240, 240, 200))
        draw.ellipse([300, 120, 340, 160], fill=(250, 250, 220))
        draw.ellipse([360, 90, 390, 120], fill=(250, 250, 220))
    elif kind == "sunset":
        for y in range(HEIGHT):
            k = y / HEIGHT
            draw.line([(0, y), (WIDTH, y)], fill=(int(250 - 60 * k), int(150 - 40 * k), int(90 + 40 * k)))
        draw.ellipse([900 + shift // 2, 300, 1040 + shift // 2, 440], fill=(255, 200, 120))
    else:
        for y in range(HEIGHT):
            k = y / HEIGHT
            draw.line([(0, y), (WIDTH, y)], fill=(int(120 + 90 * k), int(180 + 50 * k), int(245 - 20 * k)))
        draw.ellipse([150 + shift, 90, 250 + shift, 190], fill=(255, 235, 120))
        draw.ellipse([700 - shift, 140, 860 - shift, 220], fill=(255, 255, 255))
    ground = (90, 160, 80) if kind == "day" else (70, 110, 60) if kind == "sunset" else (30, 60, 40)
    draw.rectangle([0, 520, WIDTH, HEIGHT], fill=ground)
    for x in range(0, WIDTH, 160):
        draw.ellipse([x + 20, 500, x + 120, 560], fill=(70, 140, 70) if kind == "day" else (55, 100, 55))


def _character(draw: ImageDraw.ImageDraw, name: str, x: int, base: int, *, t: float,
               talking: bool, gesture: float, mouth: float | None = None) -> None:
    colors = PALETTE.get(name, PALETTE["aden"])
    bob = int(10 * math.sin(t * 3.1)) + int(3 * math.sin(t * 7.0))
    sway = int(6 * math.sin(t * 1.9))
    x += sway
    top = base - 210 + bob
    # bacaklar (hafif adım)
    step = int(10 * math.sin(t * 5.0))
    draw.rectangle([x - 34 - step, base - 70, x - 6 - step, base], fill=colors["pants"])
    draw.rectangle([x + 6 + step, base - 70, x + 34 + step, base], fill=colors["pants"])
    # gövde
    draw.rounded_rectangle([x - 46, top + 120, x + 46, base - 60], radius=18, fill=colors["shirt"])
    # kollar: jest + salınım (koordinatlar her zaman sıralı tutulur)
    swing = int(18 * math.sin(t * 5.0))
    arm_lift = max(0, min(90, int(40 * gesture)))

    def _arm(x0: int, x1: int, y_top: int, y_bottom: int) -> None:
        top_y, bottom_y = sorted((y_top, y_bottom))
        if bottom_y - top_y < 12:
            bottom_y = top_y + 12
        draw.rounded_rectangle([x0, top_y, x1, bottom_y], radius=10, fill=colors["shirt"])

    _arm(x - 74, x - 50, top + 130 - arm_lift + swing, base - 70 - arm_lift + swing)
    _arm(x + 50, x + 74, top + 130 - swing, base - 70 - swing)
    # baş
    draw.ellipse([x - 48, top, x + 48, top + 110], fill=colors["skin"])
    draw.chord([x - 48, top - 10, x + 48, top + 70], 180, 360, fill=colors["hair"])
    # gözler + kırpma
    blink = (t % 3.4) < 0.12
    eye_h = 3 if blink else 10
    draw.ellipse([x - 26, top + 52, x - 12, top + 52 + eye_h], fill=(30, 30, 30))
    draw.ellipse([x + 12, top + 52, x + 26, top + 52 + eye_h], fill=(30, 30, 30))
    # ağız: ses zarfı varsa gerçek genlik, yoksa replik zamanlaması
    if mouth is not None:
        mouth_h = 3 + int(14 * max(0.0, min(1.0, mouth)))
    else:
        mouth_h = int(4 + (12 if talking and (t * 7) % 2 < 1 else 2))
    draw.ellipse([x - 14, top + 76, x + 14, top + 76 + mouth_h], fill=(120, 40, 40))


def episode_timeline(episode: Episode) -> list[dict]:
    """Repliklerin mutlak zaman çizelgesi (ses miksajı için)."""

    rows: list[dict] = []
    clock = 0.0
    for scene in episode.scenes:
        cursor = 0.0
        for line in scene.lines:
            rows.append({
                "scene_id": scene.scene_id,
                "start": round(clock + cursor, 3),
                "end": round(clock + cursor + line.seconds, 3),
                "speaker": line.speaker,
                "text": line.text,
            })
            cursor += line.seconds
        clock += scene.duration()
    return rows


def _subtitle_band(draw: ImageDraw.ImageDraw, text: str) -> None:
    if not text:
        return
    font = _font(38)
    draw.rectangle([0, HEIGHT - 120, WIDTH, HEIGHT], fill=(0, 0, 0))
    draw.text((60, HEIGHT - 104), text[:110], font=font, fill=(255, 255, 255))


def render_episode(episode: Episode, out_dir: str | Path, *,
                   voice: str | None = None, audio: str | Path | None = None,
                   stream: bool | None = None) -> dict:
    out = Path(out_dir)
    frames_dir = out / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    out.mkdir(parents=True, exist_ok=True)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg bulunamadı")

    total_frames = int(round(episode.duration() * FPS))
    # Uzun bölümlerde binlerce PNG diske yazılmasın: kareler doğrudan ffmpeg'e
    # akıtılır. Kısa bölümlerde kareler diskte kalır (hata ayıklama kolaylığı).
    use_stream = (total_frames > 1500) if stream is None else bool(stream)
    silent_video = out / "episode.nosound.mp4"
    encoder = None
    if use_stream:
        encoder = subprocess.Popen(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe",
             "-vcodec", "png", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             str(silent_video)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    else:
        frames_dir.mkdir(parents=True, exist_ok=True)

    def emit(image) -> None:
        if encoder is not None:
            import io

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            encoder.stdin.write(buffer.getvalue())
        else:
            image.save(frames_dir / f"frame_{frame_no:05d}.png")


    planned: list[tuple[str, float, float, str, str]] = []
    srt: list[str] = []
    index = 1
    clock = 0.0
    frame_no = 0

    total_frames = int(round(episode.duration() * FPS))
    envelope: list[float] | None = None
    if audio is not None and Path(audio).is_file():
        try:
            from .studio_voice import amplitude_envelope

            envelope = amplitude_envelope(audio, fps=FPS, total_frames=total_frames)
        except Exception:  # noqa: BLE001 - zarf okunamazsa zamanlamaya düş
            envelope = None

    for scene in episode.scenes:
        scene_seconds = scene.duration()
        per_frame = 1.0 / FPS
        t = 0.0
        # sahne içi konuşma zaman çizelgesi
        schedule: list[tuple[float, float, str, str]] = []
        cursor = 0.0
        for line in scene.lines:
            schedule.append((cursor, cursor + line.seconds, line.speaker, line.text))
            cursor += line.seconds

        while t < scene_seconds - 1e-9:
            image = Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 30))
            draw = ImageDraw.Draw(image)
            shift = int(40 * math.sin(t * 0.6))
            _background(draw, scene.background, t, shift)

            current = next((s for s in schedule if s[0] <= t < s[1]), None)
            speaker = current[2] if current else ""
            caption = current[3] if current else ""

            for position, name in enumerate(scene.characters[:3]):
                x = 380 + position * 320
                gesture = math.sin(t * 1.7) if speaker == name else 0.0
                lip = None
                if envelope is not None and speaker == name and frame_no < len(envelope):
                    lip = envelope[frame_no]
                _character(draw, name, x, 560, t=t, talking=speaker == name,
                           gesture=max(0.0, gesture), mouth=lip)

            draw.text((40, 30), episode.title, font=_font(34), fill=(255, 255, 255))
            draw.text((40, 80), f"{scene.setting}", font=_font(24), fill=(235, 235, 235))
            _subtitle_band(draw, caption)
            emit(image)
            frame_no += 1
            t += per_frame

        for start, end, _speaker, text in schedule:
            srt.append(f"{index}\n{_ts(clock + start)} --> {_ts(clock + end)}\n{text}\n")
            planned.append((scene.scene_id, clock + start, clock + end, _speaker, text))
            index += 1
        clock += scene_seconds

    srt_path = out / "episode.srt"
    srt_path.write_text("\n".join(srt), encoding="utf-8")

    # konuşma zaman çizelgesi (ses miksajı ve dudak hareketi için)
    timeline = [
        {"scene_id": scene_id, "start": round(start, 3), "end": round(end, 3),
         "speaker": speaker, "text": text}
        for scene_id, start, end, speaker, text in planned
    ]
    (out / "timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")

    if encoder is not None:
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode("utf-8", "replace") if encoder.stderr else ""
        if encoder.wait(timeout=1800) != 0:
            raise RuntimeError("ffmpeg akış hatası: " + stderr[-300:])
    else:
        command = [
            ffmpeg, "-y", "-loglevel", "error",
            "-framerate", str(FPS), "-i", str(frames_dir / "frame_%05d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(silent_video),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError("ffmpeg hatası: " + (result.stderr or "")[-300:])

    video_path = out / "episode.mp4"
    if audio is not None and Path(audio).is_file():
        mux = [
            ffmpeg, "-y", "-loglevel", "error",
            "-i", str(silent_video), "-i", str(audio),
            "-c:v", "copy", "-c:a", "aac", "-strict", "-2", "-b:a", "128k",
            "-af", "apad", "-t", f"{episode.duration():.3f}",
            "-movflags", "+faststart", str(video_path),
        ]
        muxed = subprocess.run(mux, capture_output=True, text=True, timeout=1800)
        if muxed.returncode != 0:
            raise RuntimeError("ses miksajı başarısız: " + (muxed.stderr or "")[-300:])
        silent_video.unlink(missing_ok=True)
    else:
        silent_video.replace(video_path)

    manifest = {
        "title": episode.title,
        "language": episode.language,
        "scenes": len(episode.scenes),
        "duration_seconds": round(episode.duration(), 2),
        "fps": FPS,
        "resolution": [WIDTH, HEIGHT],
        "video": str(video_path),
        "subtitles": str(srt_path),
        "audio": str(audio) if audio is not None else None,
        "timeline": str(out / "timeline.json"),
        "frames": frame_no,
        "voice": voice or "none",
    }
    (out / "episode.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _probe_media(path: str | Path) -> dict:
    """Klip künyesi (fps/boyut/süre); ffprobe yoksa açık hata (fail-closed)."""

    tool = shutil.which("ffprobe")
    if not tool:
        raise RuntimeError("ffprobe bulunamadı: klip doğrulaması yapılamaz")
    proc = subprocess.run(
        [tool, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe hatası ({path}): {(proc.stderr or '')[-200:]}")
    data = json.loads(proc.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    numerator, _, denominator = str(stream.get("r_frame_rate") or "0/1").partition("/")
    try:
        fps = float(numerator) / float(denominator or 1)
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return {"width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "fps": round(fps, 3),
            "duration": round(float((data.get("format") or {}).get("duration") or 0.0), 3)}


def _normalize_clip(source: Path, target: Path, *, width: int, height: int, fps: float) -> Path:
    """Klibi teslim formatına çevirir (ölçek + letterbox + fps + yuv420p)."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg bulunamadı")
    target.parent.mkdir(parents=True, exist_ok=True)
    scale = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}")
    proc = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(source), "-vf", scale,
         "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)],
        capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(f"klip normalize edilemedi ({source}): {(proc.stderr or '')[-200:]}")
    return target


def render_from_clips(episode: Episode, clips: list[str], out_dir: str | Path, *,
                      audio: str | Path | None = None,
                      output_size: tuple[int, int] | None = None,
                      transition_seconds: float = 0.0) -> dict:
    """Klipleri bölüme çevirir; fps/boyut doğrulanır, gerekirse normalize edilir.

    Normalize edilenler `normalized` alanında kaydedilir; xfade kullanılırsa toplam
    süre `sum(durations) - (n-1)*transition` olarak hesaplanır ve senaryo süresiyle
    birlikte manifeste yazılır.
    """

    if not clips:
        raise ValueError("clips must not be empty")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg bulunamadı")

    target_size = (int(output_size[0]), int(output_size[1])) if output_size else (WIDTH, HEIGHT)
    probes = [_probe_media(clip) for clip in clips]
    target_fps = float(probes[0]["fps"] or FPS)

    normalized: list[dict] = []
    sources: list[Path] = []
    for index, (clip, probe) in enumerate(zip(clips, probes)):
        mismatch = ((probe["width"], probe["height"]) != target_size
                    or abs(probe["fps"] - target_fps) > 0.01)
        if not mismatch:
            sources.append(Path(clip))
            continue
        fixed = _normalize_clip(Path(clip), out / "normalized" / f"clip{index:02d}.mp4",
                                width=target_size[0], height=target_size[1], fps=target_fps)
        normalized.append({"clip": str(clip), "before": probe,
                           "after": _probe_media(fixed), "output": str(fixed)})
        sources.append(fixed)

    durations = [_probe_media(source)["duration"] for source in sources]
    transition = max(0.0, float(transition_seconds))
    if transition and len(sources) < 2:
        transition = 0.0
    total_seconds = round(sum(durations) - transition * (len(sources) - 1), 3)

    silent_video = out / "episode.nosound.mp4"
    ffmpeg = shutil.which("ffmpeg")
    if transition > 0:
        args: list[str] = [ffmpeg, "-y", "-loglevel", "error"]
        for source in sources:
            args += ["-i", str(source)]
        chain: list[str] = []
        last, elapsed = "0:v", 0.0
        for index in range(1, len(sources)):
            elapsed += durations[index - 1] - transition
            chain.append(f"[{last}][{index}:v]xfade=transition=fade:"
                         f"duration={transition}:offset={round(elapsed, 3)}[v{index}]")
            last = f"v{index}"
        args += ["-filter_complex", ";".join(chain), "-map", f"[{last}]",
                 "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", str(silent_video)]
        proc = subprocess.run(args, capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise RuntimeError("xfade birleştirme başarısız: " + (proc.stderr or "")[-300:])
    else:
        listing = out / "clips.txt"
        listing.write_text("".join(f"file '{path.resolve().as_posix()}'\n" for path in sources),
                           encoding="utf-8")
        proc = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(listing), "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(silent_video)],
            capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise RuntimeError("klip birleştirme başarısız: " + (proc.stderr or "")[-300:])

    timeline = episode_timeline(episode)
    srt_path = out / "episode.srt"
    srt_path.write_text("\n".join(
        f"{index}\n{_ts(row['start'])} --> {_ts(row['end'])}\n{row['text']}\n"
        for index, row in enumerate(timeline, start=1)), encoding="utf-8")
    (out / "timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False),
                                       encoding="utf-8")

    video_path = out / "episode.mp4"
    if audio is not None and Path(audio).is_file():
        muxed = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(silent_video), "-i", str(audio),
             "-c:v", "copy", "-c:a", "aac", "-strict", "-2", "-b:a", "128k", "-af", "apad",
             "-t", f"{total_seconds:.3f}", "-movflags", "+faststart", str(video_path)],
            capture_output=True, text=True, timeout=1800)
        if muxed.returncode != 0:
            raise RuntimeError("ses miksajı başarısız: " + (muxed.stderr or "")[-300:])
        silent_video.unlink(missing_ok=True)
    else:
        silent_video.replace(video_path)

    manifest = {
        "title": episode.title,
        "language": episode.language,
        "scenes": len(episode.scenes),
        "duration_seconds": total_seconds,
        "script_seconds": round(episode.duration(), 3),
        "fps": FPS,
        "resolution": list(target_size),
        "video": str(video_path),
        "subtitles": str(srt_path),
        "audio": str(audio) if audio is not None else None,
        "timeline": str(out / "timeline.json"),
        "frames": 0,
        "voice": "clips",
        "source": "clips",
        "clips": len(sources),
        "transition_seconds": transition,
        "clip_durations": durations,
        "normalized": normalized,
    }
    (out / "episode.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    return manifest

