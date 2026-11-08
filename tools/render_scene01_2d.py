"""S01E001 ilk sahne — 2D iskelet (vector puppet) teknik testi.

Yöntem: PIL ile eklem bazlı 2D puppet (kol/bacak/baş/göz/ağız ayrı),
FFmpeg ile 1920x1080 24 fps H.264. 3D değildir.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, DURATION = 1920, 1080, 24, 12
FRAMES = FPS * DURATION
SKIN = "#F5CDAA"
SKIN_SHADOW = "#E3AE86"
HAIR = "#462D1E"
HAIR_LIGHT = "#6B4630"
BLUE = "#286EC8"
BLUE_DARK = "#1E56A0"
NAVY = "#283246"
CREAM = "#F7F4EC"
CORAL = "#DC5A46"
CORAL_DARK = "#B94432"
BROWN = "#3A2A1E"
STAR = "#FFD65A"


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def endpoint(p: tuple[float, float], angle: float, length: float) -> tuple[float, float]:
    return (p[0] + math.sin(angle) * length, p[1] + math.cos(angle) * length)


def limb(draw: ImageDraw.ImageDraw, p0, p1, width: int, color: str) -> None:
    draw.line([p0, p1], fill=color, width=width)
    r = width // 2
    for p in (p0, p1):
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)


def background(draw: ImageDraw.ImageDraw, t: float) -> None:
    for y in range(H):
        k = y / H
        draw.line([(0, y), (W, y)], fill=(int(lerp(176, 244, k)), int(lerp(216, 236, k)), int(lerp(238, 210, k))))
    draw.rectangle([0, 760, W, H], fill="#8FCB6B")
    draw.rectangle([0, 760, W, 775], fill="#7BB95B")
    for x, r in ((180, 90), (350, 70), (1580, 100), (1740, 75)):
        draw.ellipse([x - r, 520 - r, x + r, 520 + r], fill="#5F9E55")
        draw.rectangle([x - 14, 520, x + 14, 800], fill="#6B4A32")
    for i in range(18):
        x = 40 + i * 105
        draw.ellipse([x, 900 + (i % 3) * 18, x + 12, 912 + (i % 3) * 18], fill="#FFF8E9")
    # kite
    kx, ky = 1480 + 20 * math.sin(t * 0.8), 190 + 14 * math.sin(t * 1.3)
    draw.polygon([(kx, ky - 80), (kx + 90, ky), (kx, ky + 90), (kx - 90, ky)], fill="#F6C949")
    draw.polygon([(kx, ky - 80), (kx + 90, ky), (kx, ky)], fill="#E64860")
    draw.polygon([(kx, ky), (kx + 90, ky), (kx, ky + 90)], fill="#4084DC")
    draw.line([(kx, ky + 90), (kx + 20, ky + 180), (kx - 10, ky + 270)], fill="#6B4630", width=4)
    for i, c in enumerate(("#E64860", "#FFD65A", "#4084DC", "#6EBE78")):
        draw.line([(kx + 20 - i * 10, ky + 180 + i * 25), (kx + 50 - i * 10, ky + 200 + i * 25)], fill=c, width=10)


def aden(draw: ImageDraw.ImageDraw, x: float, ground: float, t: float, state: dict) -> None:
    scale = 1.0
    hip = (x, ground - 190)
    shoulder = (x, ground - 360)
    neck = (x, ground - 400)
    head = (x + state["head_dx"], ground - 455)
    walk = math.sin(t * math.pi * 2.2) * state["walk"]
    # legs (behind body)
    for side, phase in ((-1, walk), (1, -walk)):
        knee = endpoint((hip[0] + side * 18, hip[1]), phase * 0.55, 95)
        ankle = endpoint(knee, -abs(phase) * 0.25 + 0.05, 92)
        limb(draw, (hip[0] + side * 18, hip[1]), knee, 26, SKIN)
        limb(draw, knee, ankle, 22, SKIN)
        draw.ellipse([ankle[0] - 22, ankle[1] - 8, ankle[0] + 26, ankle[1] + 18], fill=CREAM)
        draw.ellipse([ankle[0] - 22, ankle[1] + 8, ankle[0] + 26, ankle[1] + 18], fill=BLUE)
    # torso
    draw.rounded_rectangle([shoulder[0] - 62, shoulder[1], hip[0] + 62, hip[1] + 10], 38, fill=BLUE)
    draw.polygon([(x - 62, shoulder[1] + 20), (x + 62, shoulder[1] + 20), (x + 62, shoulder[1] + 50), (x - 62, shoulder[1] + 50)], fill=BLUE_DARK)
    # kite print
    draw.polygon([(x - 12, shoulder[1] + 55), (x + 16, shoulder[1] + 62), (x - 4, shoulder[1] + 94)], fill="#F6C949")
    # shorts
    draw.rounded_rectangle([hip[0] - 56, hip[1] - 20, hip[0] + 56, hip[1] + 70], 20, fill=NAVY)
    # arms
    swing = math.sin(t * math.pi * 2.2) * 0.55 * state["walk"]
    for side, phase in ((-1, -swing), (1, swing)):
        sx, sy = x + side * 58, shoulder[1] + 18
        if state["wave"] and side == 1:
            elbow = (sx + 55, sy - 70)
            hand = (elbow[0] + 25 + 18 * math.sin(t * 9), elbow[1] - 105)
        else:
            elbow = endpoint((sx, sy), phase * 0.7 + side * 0.25, 90)
            hand = endpoint(elbow, phase * 0.9 + side * 0.2, 85)
        limb(draw, (sx, sy), elbow, 24, BLUE)
        limb(draw, elbow, hand, 20, SKIN)
        draw.ellipse([hand[0] - 14, hand[1] - 14, hand[0] + 14, hand[1] + 14], fill=SKIN)
    # head
    draw.rectangle([neck[0] - 14, neck[1], neck[0] + 14, head[1] + 60], fill=SKIN_SHADOW)
    draw.ellipse([head[0] - 78, head[1] - 78, head[0] + 78, head[1] + 78], fill=SKIN)
    # hair back + fringe
    draw.ellipse([head[0] - 88, head[1] - 92, head[0] + 88, head[1] + 60], fill=HAIR)
    draw.polygon([(head[0] - 78, head[1] - 20), (head[0] - 55, head[1] - 86), (head[0] - 10, head[1] - 96),
                  (head[0] + 45, head[1] - 80), (head[0] + 62, head[1] - 30), (head[0] + 30, head[1] - 62),
                  (head[0] - 12, head[1] - 58), (head[0] - 42, head[1] - 30)], fill=HAIR)
    draw.arc([head[0] - 78, head[1] - 30, head[0] + 20, head[1] + 70], 120, 250, fill=HAIR, width=18)
    # star clip
    sx, sy = head[0] - 52, head[1] - 74
    draw.polygon([(sx + 14 * math.cos(math.pi / 2 + i * 4 * math.pi / 5),
                   sy + 14 * math.sin(math.pi / 2 + i * 4 * math.pi / 5)) for i in range(5)], fill=STAR)
    # eyes
    look = state["look"]
    for side in (-1, 1):
        ex = head[0] + side * 30
        draw.ellipse([ex - 22, head[1] - 20, ex + 22, head[1] + 24], fill="#FFFFFF")
        draw.ellipse([ex - 11 + look * 4, head[1] + 0, ex + 11 + look * 4, head[1] + 22], fill=BROWN)
        draw.ellipse([ex - 4 + look * 4, head[1] + 4, ex + 2 + look * 4, head[1] + 10], fill="#FFFFFF")
        if state["blink"]:
            draw.ellipse([ex - 24, head[1] - 22, ex + 24, head[1] + 26], fill=SKIN)
        draw.arc([ex - 22, head[1] - 42, ex + 22, head[1] - 14], 200, 340, fill=HAIR, width=6)
    draw.ellipse([head[0] - 6, head[1] + 20, head[0] + 6, head[1] + 30], fill=SKIN_SHADOW)
    # freckles
    for fx, fy in ((-12, 30), (-22, 38), (-4, 42)):
        draw.ellipse([head[0] + fx, head[1] + fy, head[0] + fx + 6, head[1] + fy + 6], fill="#B9784F")
    # mouth
    if state["talk"] > 0:
        shape = state.get("talk_shape", 0)
        widths = {0: (14, 10), 1: (26, 20), 2: (10, 26), 3: (24, 14)}
        w, h = widths.get(shape, (18, 16))
        draw.ellipse([head[0] - w, head[1] + 48, head[0] + w, head[1] + 48 + h], fill="#8A3B3B")
        draw.ellipse([head[0] - w * 0.5, head[1] + 54, head[0] + w * 0.5, head[1] + 54 + h * 0.5], fill="#F09A9A")
    else:
        draw.arc([head[0] - 26, head[1] + 38, head[0] + 26, head[1] + 78], 20, 160, fill="#8A3B3B", width=7)


def kaan(draw: ImageDraw.ImageDraw, x: float, ground: float, t: float, state: dict) -> None:
    crawl = state["crawl"]
    bob = math.sin(t * 7) * 5
    body_y = ground - 70 + bob
    # limbs
    for side in (-1, 1):
        phase = math.sin(t * 7 + (0 if side < 0 else math.pi)) * 0.7
        hip = (x + side * 30, body_y + 30)
        knee = endpoint(hip, 0.9 + phase * 0.4, 55)
        foot = endpoint(knee, 0.4, 45)
        limb(draw, hip, knee, 22, "#E8B48C")
        limb(draw, knee, foot, 18, "#E8B48C")
        shoulder = (x + 70 + side * 18, body_y - 20)
        elbow = endpoint(shoulder, 0.8 + phase * 0.5, 50)
        hand = endpoint(elbow, 0.6, 45)
        limb(draw, shoulder, elbow, 20, CORAL)
        limb(draw, elbow, hand, 16, "#E8B48C")
        draw.ellipse([hand[0] - 11, hand[1] - 11, hand[0] + 11, hand[1] + 11], fill="#E8B48C")
    # body
    draw.ellipse([x - 55, body_y - 45, x + 85, body_y + 50], fill=CORAL)
    draw.rounded_rectangle([x - 40, body_y + 10, x + 55, body_y + 55], 16, fill="#3C3C5A")
    # head
    head = (x + 95, body_y - 80 + bob)
    draw.ellipse([head[0] - 62, head[1] - 62, head[0] + 62, head[1] + 62], fill=SKIN)
    for i in range(7):
        a = i * math.pi / 3
        cx = head[0] + math.cos(a) * 45
        cy = head[1] - 40 + math.sin(a) * 28
        draw.ellipse([cx - 22, cy - 18, cx + 22, cy + 18], fill=HAIR)
    # eyes
    for side in (-1, 1):
        ex = head[0] + side * 24
        draw.ellipse([ex - 17, head[1] - 12, ex + 17, head[1] + 22], fill="#FFFFFF")
        draw.ellipse([ex - 9, head[1] + 2, ex + 9, head[1] + 20], fill=BROWN)
        draw.ellipse([ex - 3, head[1] + 5, ex + 2, head[1] + 10], fill="#FFFFFF")
        if state["blink"]:
            draw.ellipse([ex - 18, head[1] - 14, ex + 18, head[1] + 24], fill=SKIN)
    draw.ellipse([head[0] - 5, head[1] + 18, head[0] + 5, head[1] + 26], fill=SKIN_SHADOW)
    draw.arc([head[0] - 22, head[1] + 30, head[0] + 22, head[1] + 66], 15, 165, fill="#8A3B3B", width=6)


def frame(t: float) -> Image.Image:
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    background(draw, t)
    # Aden: 0-4 walk, 4-6 stop/wave, 6-9 talk, 9-12 look at kite
    ax = lerp(380, 780, ease(t / 4)) if t < 4 else 780
    walk = 1.0 if t < 4 else 0.0
    wave = 1.0 if 4.2 <= t <= 6.2 else 0.0
    talk = max(0.0, min(1.0, math.sin((t - 6) * 12))) if 6 <= t <= 9 else 0.0
    talk_shape = int((t - 6) * 8) % 4 if 6 <= t <= 9 else 0
    look = 1.0 if 4 <= t <= 9.5 else 0.0
    blink = 1 if (t % 3.2) < 0.12 else 0
    aden_state = {"walk": walk, "wave": wave, "talk": talk, "talk_shape": talk_shape,
                  "look": look, "blink": blink, "head_dx": 18 if t >= 4 else 0}
    draw.ellipse([ax - 90, 930, ax + 90, 965], fill="#6E9E55")
    aden(draw, ax, 920, t, aden_state)
    # Kaan: crawl toward Aden (0-4), look (4-10), kite (10-12)
    kx = lerp(1180, 1000, ease(t / 3)) if t < 4 else 1000
    kaan_blink = 1 if (t % 2.8 + 0.4) < 0.12 else 0
    draw.ellipse([kx - 10, 935, kx + 150, 965], fill="#6E9E55")
    kaan(draw, kx, 930, t, {"crawl": 1, "blink": kaan_blink})
    # kontrollü yavaş push-in
    zoom = 1.0 + 0.04 * ease(t / DURATION)
    box = ((W - W / zoom) / 2, (H - H / zoom) / 2, (W + W / zoom) / 2, (H + H / zoom) / 2)
    return image.crop(box).resize((W, H), Image.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "S01E001-SCENE01-2D-RIG"))
    args = parser.parse_args(argv)
    out = Path(args.out)
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for index in range(FRAMES):
        frame(index / FPS).save(frames_dir / f"frame-{index:04d}.png")
    video = out / "S01E001-SCENE01-2D-RIG-1080p24.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames_dir / "frame-%04d.png"),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-r", str(FPS), "-movflags", "+faststart", "-an", str(video)],
                   check=True, capture_output=True)
    meta = {
        "schema": "ahos.studio.2d-rig-scene.v1",
        "status": "TECHNICAL_TEST_PENDING_REVIEW",
        "method": "2D vector puppet (PIL) with independent limb/head/eye/mouth joints; FFmpeg encode",
        "is_3d": False,
        "video": str(video.relative_to(ROOT)).replace("\\", "/"),
        "fps": FPS, "duration_seconds": DURATION, "frames": FRAMES,
        "resolution": [W, H], "audio": "SILENT",
        "characters": ["aden", "kaan"],
        "source_reference": "studio/reference/owner_accepted_roster_v1/characters/01_aden.png,02_kaan.png",
        "joints": ["hip", "knee", "ankle", "shoulder", "elbow", "hand", "neck", "head", "eyes", "mouth"],
        "identity_note": "Vector approximation from accepted roster; face likeness not owner-approved.",
        "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
    }
    (out / "scene-manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: meta[key] for key in ("status", "video", "sha256", "frames")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
