#!/usr/bin/env python3
"""AHOS Shorts: bölümden 9:16 kısa kesit (kanca ilk saniyelerde). Kaynak: vibe.kafasi analizi.
En 'hareketli' pencereyi beat_sheet'ten seçer (replik yoğunluğu + fx/props + duygu), ffmpeg ile ortadan 9:16 kırpar.
Yükleme yapmaz."""
import argparse, json, os, shutil, subprocess, sys

HOOK_EMO = ("surprise", "şaşkın", "laugh", "güldü", "fear", "korku", "excited", "heyecan", "angry", "kızgın")


def score(b):
    s = 1.0 if (b.get("line") or b.get("text") or b.get("dialogue")) else 0.0
    s += 0.6 * len(b.get("fx") or []) + 0.3 * len(b.get("props") or [])
    if any(k in str(b.get("emotion", "")).lower() for k in HOOK_EMO):
        s += 1.0
    return s


def pick_window(beats, length=40.0):
    """Skoru en yüksek [t0, t0+length] penceresi (beat başlangıçlarında)."""
    if not beats:
        return None
    end = float(beats[-1]["t_end"]); length = min(length, end)
    best = (-1.0, 0.0)
    for b in beats:
        t0 = float(b["t_start"])
        if t0 + length > end + 1e-6:
            t0 = max(0.0, end - length)
        sc = sum(score(x) for x in beats if float(x["t_start"]) < t0 + length and float(x["t_end"]) > t0)
        if sc > best[0]:
            best = (sc, t0)
    return {"t0": round(best[1], 2), "t1": round(best[1] + length, 2), "score": round(best[0], 2)}


def run(episode_dir, video, length=40.0, runner=subprocess.run):
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    w = pick_window(sheet["beats"], length)
    if not w:
        return {"status": "BLOCKED", "error": "NO_BEATS"}
    out = os.path.join(episode_dir, "render", "short_%d_%d.mp4" % (w["t0"], w["t1"]))
    cmd = [shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-ss", str(w["t0"]), "-i", video, "-t", str(length),
           "-vf", "crop=ih*9/16:ih,scale=1080:1920,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-strict", "-2", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out]
    r = runner(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out)
    return {"status": "PASSED" if ok else "BLOCKED", "short": out if ok else None, "window": w,
            "note": "orta kırpma; karakter kadrajın dışında kalabilir -> insan/QA gözü gerekir; yüklenmedi"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--episode-dir", required=True); ap.add_argument("--video", required=True)
    ap.add_argument("--length", type=float, default=40.0)
    a = ap.parse_args(); print(json.dumps(run(a.episode_dir, a.video, a.length), ensure_ascii=False, indent=1))
