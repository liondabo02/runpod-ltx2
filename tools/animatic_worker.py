#!/usr/bin/env python3
"""AHOS Animatik işçisi (kurgu aşamasının ilk hâli, diziden bağımsız).

beat_sheet.json + voice_manifest.json -> her vuruş için storyboard kartı (PNG) + zamanında yerleştirilmiş ses
-> tek bir izlenebilir animatic.mp4. Ücretsiz (PIL + ffmpeg). Bu bir ANİMATİKTİR, final film DEĞİLDİR:
karakter modelleri/animasyon bağlanana kadar bölümün ritmini, süresini ve sesini denetlemek içindir.

Kullanım: python tools/animatic_worker.py --episode-dir series/<id>/episodes/e001 [--series series/<id>/series-bible.json]
"""
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, textwrap, wave, struct

W, H = 1280, 720
FPS = int(os.environ.get("AHOS_FPS", "12"))
PALETTE = ["#8ecae6", "#ffb703", "#a7c957", "#f4a6c0", "#cdb4db", "#ffd6a5", "#bde0fe", "#caffbf"]
FONTS = [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]


def font(size):
    from PIL import ImageFont
    for f in FONTS:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    raise RuntimeError("Türkçe karakter destekli yazı tipi bulunamadı (Arial/DejaVu)")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def card(beat, idx, total, loc_color, path, title=""):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (W, H), loc_color); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 70], fill="#1d3557")
    d.text((24, 16), f"{title}  ·  vuruş {idx + 1}/{total}  ·  {beat['t_start']:.0f}-{beat['t_end']:.0f} sn", font=font(30), fill="white")
    y = 100
    d.text((40, y), f"Mekân: {beat.get('location', '')}   Işık: {beat.get('light_time', '')}", font=font(26), fill="#1d3557"); y += 50
    d.text((40, y), "Karakterler: " + ", ".join(beat.get("characters", [])), font=font(26), fill="#1d3557"); y += 60
    for ln in textwrap.wrap(str(beat.get("action", "")), 62)[:8]:
        d.text((40, y), ln, font=font(30), fill="#111"); y += 40
    y = max(y + 10, 470)
    dl = str(beat.get("dialogue", "") or "")
    if dl:
        d.rounded_rectangle([30, y, W - 30, H - 70], 18, fill="white")
        yy = y + 14
        lines = [w for part in dl.replace("\n", " | ").split(" | ") for w in (textwrap.wrap(part, 70) or [""])]
        for ln in lines[:5]:
            d.text((50, yy), ln, font=font(28), fill="#222"); yy += 36
    d.text((24, H - 52), f"Kamera: {beat.get('camera', '')}   Ses: {beat.get('sound', '')}"[:110], font=font(22), fill="#1d3557")
    im.save(path)


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        return w.getframerate(), struct.unpack("<%dh" % w.getnframes(), w.readframes(w.getnframes()))


def build_timeline(episode_dir, items, beats, total_s, sr=16000):
    _cur = {}
    for it in items:  # aynı vuruştaki satırlar art arda
        if "start_s" not in it:
            it["start_s"] = round(_cur.get(it["beat"], 0.2), 2)
        _cur[it["beat"]] = it["start_s"] + float(it.get("duration_s", 0)) + 0.3
    buf = [0] * int(total_s * sr)
    for it in items:
        wp = os.path.join(episode_dir, it["wav"].replace("\\", "/"))
        if not os.path.exists(wp):
            continue
        rate, data = read_wav(wp)
        if rate != sr: continue
        off = int(float(beats[it["beat"]]["t_start"]) * sr) + int(float(it.get("start_s", 0.2)) * sr)
        for i, v in enumerate(data):
            j = off + i
            if j >= len(buf): break
            x = buf[j] + v
            buf[j] = max(-32768, min(32767, x))
    out = os.path.join(episode_dir, "animatic", "timeline.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(struct.pack("<%dh" % len(buf), *buf))
    return out


def probe(mp4):
    ff = shutil.which("ffprobe") or "ffprobe"
    r = subprocess.run([ff, "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                        "-of", "json", mp4], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    return {"duration": float(j["format"]["duration"]), "streams": [s["codec_type"] for s in j["streams"]],
            "size": next(((s["width"], s["height"]) for s in j["streams"] if s["codec_type"] == "video"), None)}


def run(episode_dir, bible=None):
    episode_dir = os.path.abspath(episode_dir)
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    vm_path = os.path.join(episode_dir, "voice_manifest.json")
    items = json.load(open(vm_path, encoding="utf-8")).get("items", []) if os.path.exists(vm_path) else []
    beats = sheet["beats"]; total = float(beats[-1]["t_end"])
    adir = os.path.join(episode_dir, "animatic"); fdir = os.path.join(adir, "frames"); os.makedirs(fdir, exist_ok=True)
    locs = sorted({b.get("location", "") for b in beats}); colors = {l: PALETTE[i % len(PALETTE)] for i, l in enumerate(locs)}
    lst = []
    for i, b in enumerate(beats):
        p = os.path.join(fdir, f"b{i:03d}.png")
        card(b, i, len(beats), colors[b.get("location", "")], p, sheet.get("title", ""))
        lst.append((p, float(b["t_end"]) - float(b["t_start"])))
    concat = os.path.join(adir, "frames.txt")
    with open(concat, "w", encoding="utf-8") as f:
        for p, d in lst:
            f.write(f"file '{p.replace(chr(92), '/')}'\nduration {d:.3f}\n")
        f.write(f"file '{lst[-1][0].replace(chr(92), '/')}'\n")
    wav = build_timeline(episode_dir, items, beats, total) if items else None
    mp4 = os.path.join(episode_dir, "animatic.mp4")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat]
    cmd += (["-i", wav] if wav else ["-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono"])
    cmd += ["-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-strict", "-2", "-c:a", "aac", "-b:a", "96k", "-t", f"{total:.2f}", "-movflags", "+faststart", mp4]
    subprocess.run(cmd, check=True)
    pr = probe(mp4); problems = []
    if abs(pr["duration"] - total) > 1.5: problems.append(f"süre {pr['duration']:.1f}s, hedef {total:.0f}s")
    if "audio" not in pr["streams"]: problems.append("ses akışı yok")
    if "video" not in pr["streams"]: problems.append("video akışı yok")
    man = {"stage": "animatic", "status": "PASSED" if not problems else "NEEDS_REVISION", "cost_eur": 0,
           "note": "ANİMATİK: storyboard kartları + gerçek diyalog sesi; final film değildir",
           "duration_s": round(pr["duration"], 2), "resolution": pr["size"], "voiced_lines": len(items),
           "problems": problems, "artifact": {"path": "animatic.mp4", "sha256": sha(mp4)},
           "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    with open(os.path.join(episode_dir, "animatic_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    return man


def main():
    p = argparse.ArgumentParser(); p.add_argument("--episode-dir", required=True); p.add_argument("--series")
    a = p.parse_args()
    m = run(a.episode_dir)
    print(f"Animatik: {m['status']} | {m['duration_s']} sn | {m['resolution']} | seslendirilen satır: {m['voiced_lines']}")
    for x in m["problems"]: print(" -", x)
    print("Dosya:", os.path.join(a.episode_dir, "animatic.mp4"))


if __name__ == "__main__":
    main()
