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
    """Katmanlı (paralaks) arka plan: uzak silüet → orta katman → zemin.

    CN mantığı: düz renkler, belirgin silüetler, önde koyu/arkada açık değer.
    """

    if kind == "night":
        sky_top, sky_bottom = (18, 24, 52), (46, 62, 104)
        ground, far, mid = (26, 40, 46), (34, 52, 70), (22, 36, 40)
        lamp = (246, 238, 206)
    elif kind == "sunset":
        sky_top, sky_bottom = (232, 116, 88), (255, 208, 150)
        ground, far, mid = (128, 86, 72), (168, 110, 92), (96, 68, 58)
        lamp = (255, 210, 140)
    else:
        sky_top, sky_bottom = (108, 186, 236), (214, 238, 250)
        ground, far, mid = (92, 168, 96), (128, 196, 132), (64, 132, 72)
        lamp = (255, 238, 140)

    for y in range(HEIGHT):
        ratio = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)],
                  fill=(int(sky_top[0] + (sky_bottom[0] - sky_top[0]) * ratio),
                        int(sky_top[1] + (sky_bottom[1] - sky_top[1]) * ratio),
                        int(sky_top[2] + (sky_bottom[2] - sky_top[2]) * ratio)))

    # uzak katman (yavaş): tepeler
    far_shift = int(shift * 0.25)
    for index in range(-1, 5):
        cx = index * 420 + far_shift
        draw.ellipse([cx, 380, cx + 520, 700], fill=far)

    # gökyüzü nesnesi (güneş/ay) — orta hızda
    sun_x = 980 + int(shift * 0.5)
    if kind == "night":
        draw.ellipse([sun_x, 90, sun_x + 110, 200], fill=lamp)
        draw.ellipse([sun_x + 34, 100, sun_x + 96, 168], fill=far)
    else:
        draw.ellipse([sun_x, 80, sun_x + 130, 210], fill=lamp)

    # orta katman: ağaç/tepe silüetleri (orta hız)
    mid_shift = int(shift * 0.6)
    for index in range(-1, 8):
        tx = index * 240 + mid_shift
        draw.ellipse([tx, 430, tx + 200, 620], fill=mid)
        draw.rectangle([tx + 88, 520, tx + 112, 620], fill=_shade(mid, 0.8))

    # ön katman: zemin + çim tutamları (hızlı)
    ground_y = 560
    draw.rectangle([0, ground_y, WIDTH, HEIGHT], fill=ground)
    near_shift = int(shift * 1.0)
    for x in range(-160, WIDTH + 160, 120):
        bx = x + (near_shift % 120)
        draw.ellipse([bx, ground_y - 16, bx + 120, ground_y + 44], fill=_shade(ground, 0.9))
        for blade in range(3):
            gx = bx + 24 + blade * 30
            draw.line([gx, ground_y + 6, gx + 6, ground_y - 26],
                      fill=_shade(ground, 1.25), width=5)


def _shade(color, factor: float):
    """Düz renk paletinden gölge/vurgu tonu üretir (gradyan yok)."""

    return tuple(max(0, min(255, int(channel * factor))) for channel in color)


OUTLINE = (26, 26, 31)
OUTLINE_WIDTH = 4


def _draw_character(draw: ImageDraw.ImageDraw, name: str, x: int, base: int, *, t: float,
                    talking: bool, gesture: float, mouth: float | None = None) -> None:
    """CN tarzı karakter: kalın dış kontur, iri gözler, belirgin siluet."""

    colors = PALETTE.get(name, PALETTE["aden"])
    bob = int(10 * math.sin(t * 3.1)) + int(3 * math.sin(t * 7.0))
    sway = int(6 * math.sin(t * 1.9))
    x += sway
    top = base - 220 + bob

    shirt, pants = colors["shirt"], colors["pants"]
    shirt_dark = _shade(shirt, 0.82)
    skin = colors["skin"]
    hair = colors["hair"]

    # zemin gölgesi (karakteri zemine oturtur)
    draw.ellipse([x - 62, base - 12, x + 62, base + 10], fill=(0, 0, 0, 55))

    # bacaklar (abartılı ayak, konturlu)
    step = int(10 * math.sin(t * 5.0))
    for side, offset in ((-1, -step), (1, step)):
        draw.rounded_rectangle([x + side * 34 - 18 + offset, base - 76,
                                x + side * 34 + 18 + offset, base - 8],
                               radius=10, fill=pants, outline=OUTLINE, width=3)
        draw.rounded_rectangle([x + side * 34 - 24 + offset, base - 14,
                                x + side * 34 + 26 + offset, base + 4],
                               radius=8, fill=_shade(pants, 0.7), outline=OUTLINE, width=3)

    # gövde + gölge yarısı
    draw.rounded_rectangle([x - 50, top + 116, x + 50, base - 62], radius=20,
                           fill=shirt, outline=OUTLINE, width=OUTLINE_WIDTH)
    draw.rounded_rectangle([x + 4, top + 122, x + 46, base - 68], radius=16,
                           fill=shirt_dark)

    # kollar: jest + salınım, abartılı el
    swing = int(18 * math.sin(t * 5.0))
    arm_lift = max(0, min(96, int(44 * gesture)))

    def _arm(inner: int, outer: int, y_top: int, y_bottom: int) -> None:
        top_y, bottom_y = sorted((y_top, y_bottom))
        if bottom_y - top_y < 14:
            bottom_y = top_y + 14
        draw.rounded_rectangle([inner, top_y, outer, bottom_y], radius=11,
                               fill=shirt, outline=OUTLINE, width=3)
        hand_x = (inner + outer) // 2
        draw.ellipse([hand_x - 14, bottom_y - 8, hand_x + 14, bottom_y + 20],
                     fill=skin, outline=OUTLINE, width=3)

    _arm(x - 78, x - 52, top + 128 - arm_lift + swing, base - 74 - arm_lift + swing)
    _arm(x + 52, x + 78, top + 128 - swing, base - 74 - swing)

    # baş (iri) + saç silueti (isme göre farklı: tek bakışta ayırt edilir)
    head = 58
    draw.ellipse([x - head, top - 6, x + head, top + 116], fill=skin,
                 outline=OUTLINE, width=OUTLINE_WIDTH)
    variant = sum(ord(ch) for ch in str(name)) % 3
    if variant == 0:  # kısa küt saç
        draw.chord([x - head - 4, top - 18, x + head + 4, top + 78], 180, 360,
                   fill=hair, outline=OUTLINE, width=3)
    elif variant == 1:  # iki yanda topuz
        draw.chord([x - head - 4, top - 14, x + head + 4, top + 70], 180, 360,
                   fill=hair, outline=OUTLINE, width=3)
        for side in (-1, 1):
            draw.ellipse([x + side * (head - 6) - 18, top + 14,
                          x + side * (head - 6) + 18, top + 50],
                         fill=hair, outline=OUTLINE, width=3)
    else:  # dağınık / dik saç
        spikes = [(x - head, top + 6), (x - 30, top - 26), (x - 6, top + 2),
                  (x + 18, top - 30), (x + head, top + 4), (x + head, top + 34),
                  (x - head, top + 34)]
        draw.polygon(spikes, fill=hair, outline=OUTLINE, width=3)

    # gözler: iri beyaz + bebek + konuşurken kısılan kaş
    blink = (t % 4.2) < 0.10
    eye_w, eye_h = 30, (4 if blink else 34)
    for side in (-1, 1):
        eye_x = x + side * 26
        draw.ellipse([eye_x - eye_w // 2, top + 46, eye_x + eye_w // 2, top + 46 + eye_h],
                     fill=(255, 255, 255), outline=OUTLINE, width=3)
        if not blink:
            draw.ellipse([eye_x - 8, top + 56, eye_x + 8, top + 76], fill=(28, 24, 24))
            draw.ellipse([eye_x - 3, top + 58, eye_x + 3, top + 64], fill=(255, 255, 255))
    if not blink:
        for side in (-1, 1):
            brow_y = top + 34 - (4 if talking else 0)
            draw.line([x + side * 26 - 15, brow_y, x + side * 26 + 15, brow_y],
                      fill=OUTLINE, width=4)

    # ağız: ses zarfı varsa gerçek genlik, yoksa 3 kademeli CN açıklığı
    if mouth is not None:
        level = max(0.0, min(1.0, mouth))
    else:
        level = 0.65 if talking and (t * 7) % 2 < 1 else 0.0
    # CN: sürekli sinüs değil, 3 kademeli açıklık (kapalı / yarım / tam)
    mouth_h = 4 if level < 0.2 else (14 if level < 0.6 else 26)
    draw.ellipse([x - 16, top + 84, x + 16, top + 84 + mouth_h],
                 fill=(150, 46, 46), outline=OUTLINE, width=3)
    # yanak (vurgu tonu)
    for side in (-1, 1):
        cheek = x + side * 40
        draw.ellipse([cheek - 11, top + 78, cheek + 11, top + 96],
                     fill=_shade((240, 156, 146), 1.0))


def _character(draw: ImageDraw.ImageDraw, name: str, x: int, base: int, *, t: float,
               talking: bool, gesture: float, mouth: float | None = None,
               scale: float = 1.0) -> None:
    """Karakteri çiz; scale != 1 ise tüm gövdeyi (x, base) etrafında ölçekle.

    Ölçekleme, çizim koordinatlarını tek tek değiştirmek yerine karakteri
    saydam bir katmana çizip çapa noktası etrafında yeniden boyutlandırır.
    Böylece scale=1.0 birebir eski davranışı korur; tüm yarıçaplar, uzuvlar,
    yüz ve kontur kalınlıkları aynı oranda ölçeklenir.
    """

    if abs(float(scale) - 1.0) < 1e-9:
        _draw_character(draw, name, x, base, t=t, talking=talking,
                        gesture=gesture, mouth=mouth)
        return

    if scale <= 0:
        raise ValueError("scale must be > 0")

    target = draw._image
    overlay = Image.new("RGBA", target.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    _draw_character(overlay_draw, name, x, base, t=t, talking=talking,
                    gesture=gesture, mouth=mouth)

    pad_x, pad_y = 220, 360
    left = max(0, x - pad_x)
    top_ = max(0, base - pad_y)
    right = min(target.width, x + pad_x)
    bottom = min(target.height, base + 40)
    region = overlay.crop((left, top_, right, bottom))
    resized = region.resize(
        (max(1, int(round(region.width * scale))),
         max(1, int(round(region.height * scale)))),
        Image.Resampling.LANCZOS,
    )
    dest_x = int(round(x - (x - left) * scale))
    dest_y = int(round(base - (base - top_) * scale))
    target.paste(resized, (dest_x, dest_y), resized)


def _shake_offset(envelope: list[float] | None, frame_no: int) -> int:
    """Ses zirvelerinde deterministik ±3 px shake; sessizlikte 0."""

    if not envelope or frame_no < 0 or frame_no >= len(envelope):
        return 0
    peak = max(envelope)
    if peak <= 0:
        return 0
    if envelope[frame_no] <= 0.8 * peak:
        return 0
    return 3 if (frame_no // 2) % 2 == 0 else -3



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


def _flash_alpha(t_local: float) -> float:
    """Sahne başında 1 karelik beyaz flash (CN geçişi). 1.0 → tam beyaz kare."""

    frame = 1.0 / float(FPS)
    if t_local < frame:
        return 1.0
    return 0.0


def _subtitle_band(draw: ImageDraw.ImageDraw, text: str, *, speaker: str = "") -> None:
    """CN tarzı altyazı: konturlu kalın yazı + konuşanın renginde isim şeridi."""

    if not text:
        return
    band_h = 96
    top = HEIGHT - band_h
    draw.rectangle([0, top, WIDTH, HEIGHT], fill=(18, 18, 24))
    accent = PALETTE.get(speaker, PALETTE["aden"])["shirt"]
    draw.rectangle([0, top, WIDTH, top + 7], fill=accent)
    if speaker:
        name_font = _font(26)
        label = speaker.upper()
        box = draw.textbbox((0, 0), label, font=name_font)
        pad = 14
        draw.rounded_rectangle([36, top + 12, 36 + (box[2] - box[0]) + pad * 2, top + 44],
                               radius=9, fill=accent)
        draw.text((36 + pad, top + 15), label, font=name_font, fill=(16, 16, 20))

    font = _font(34)
    y = top + (40 if speaker else 22)
    # kontur: 4 yönde OFFSET, sonra dolgu (CN başlık stili)
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        draw.text((60 + dx, y + dy), text[:110], font=font, fill=OUTLINE)
    draw.text((60, y), text[:110], font=font, fill=(255, 255, 255))


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
        scene_frames = max(1, int(round(scene_seconds * FPS)))
        scene_frame = 0
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

            # Punch-in: çekim boyunca 1.00 -> 1.06; kare bazlı deterministik.
            progress = min(1.0, max(0.0, scene_frame / max(1, scene_frames - 1)))
            scale = 1.0 + 0.06 * progress
            shake_x = _shake_offset(envelope, frame_no)

            for position, name in enumerate(scene.characters[:3]):
                x = 380 + position * 320 + shake_x
                gesture = math.sin(t * 1.7) if speaker == name else 0.0
                lip = None
                if envelope is not None and speaker == name and frame_no < len(envelope):
                    lip = envelope[frame_no]
                _character(draw, name, x, 560, t=t, talking=speaker == name,
                           gesture=max(0.0, gesture), mouth=lip, scale=scale)

            draw.text((40, 30), episode.title, font=_font(34), fill=(255, 255, 255))
            draw.text((40, 80), f"{scene.setting}", font=_font(24), fill=(235, 235, 235))
            _subtitle_band(draw, caption, speaker=speaker)
            if _flash_alpha(t) >= 1.0:
                draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(255, 255, 255))
            emit(image)
            frame_no += 1
            scene_frame += 1
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
    partial_video = out / "episode.partial.mp4"
    if audio is not None and Path(audio).is_file():
        muxed = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(silent_video), "-i", str(audio),
             "-c:v", "copy", "-c:a", "aac", "-strict", "-2", "-b:a", "128k", "-af", "apad",
             "-t", f"{total_seconds:.3f}", "-movflags", "+faststart", str(partial_video)],
            capture_output=True, text=True, timeout=1800)
        if muxed.returncode != 0:
            partial_video.unlink(missing_ok=True)
            raise RuntimeError("ses miksajı başarısız: " + (muxed.stderr or "")[-300:])
        silent_video.unlink(missing_ok=True)
    else:
        silent_video.replace(partial_video)
    # Crash safety: yarım dosya asla `episode.mp4` adıyla görünmez.
    partial_video.replace(video_path)

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

