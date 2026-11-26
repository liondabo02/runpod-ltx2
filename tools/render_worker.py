#!/usr/bin/env python3
"""AHOS Render işçisi (diziden bağımsız): plan -> Blender kareleri -> ffmpeg ile sesli klip.

Kullanım:
  python tools/render_worker.py --episode-dir out/test003 --series series/test-bulut-bahcesi/series-bible.json --from 0 --to 10
Kareler kaldığı yerden devam eder. Süre/kare ölçülür ve 8 dakikalık bölüm için tahmin yazılır.
"""
import argparse, glob, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import shot_planner as sp  # noqa: E402
import animatic_worker as aw  # noqa: E402
import puppet2d as pp2  # noqa: E402
import render2d as r2  # noqa: E402

BLENDER_CANDS = [os.environ.get("BLENDER_EXE", ""), r"C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe",
                 shutil.which("blender") or ""]



_LOUD = None


def _loud_filter():
    """Eski ffmpeg derlemelerinde loudnorm yok: sırayla loudnorm, dynaudnorm, volume dener."""
    global _LOUD
    if _LOUD is None:
        try:
            out = subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-filters"],
                                 capture_output=True, text=True).stdout
        except Exception:  # noqa: BLE001
            out = ""
        if " loudnorm " in out:
            _LOUD = "loudnorm=I=-16:TP=-1.5:LRA=11"
        elif " dynaudnorm " in out:
            _LOUD = "dynaudnorm=f=250:g=15,alimiter=limit=0.9" if " alimiter " in out else "dynaudnorm=f=250:g=15"
        else:
            _LOUD = "volume=1.5"
    return _LOUD

def find_blender():
    return next((c for c in BLENDER_CANDS if c and os.path.exists(c)), None)


def split_by_scene(sheet, t0, t1):
    """Pencereyi mekân değişimlerinde böler (her parça tek mekân)."""
    segs, cur = [], None
    for b in sheet["beats"]:
        ts, te = max(float(b["t_start"]), t0), min(float(b["t_end"]), t1)
        if te <= ts:
            continue
        loc = b.get("location")
        if cur and cur[2] == loc and abs(cur[1] - ts) < 1e-6:
            cur[1] = te
        else:
            cur = [ts, te, loc]; segs.append(cur)
    return segs


def run(episode_dir, bible, t0, t1, series_dir, engine="2d", samples=16, runner=subprocess.run):
    episode_dir = os.path.abspath(episode_dir)
    assets = os.path.join(series_dir, "assets")
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    rdir = os.path.join(episode_dir, "render"); os.makedirs(rdir, exist_ok=True)
    import object_state, setpieces2d
    bad = []                                            # ön kontrol: geçersiz nesne izi (ışınlanma, havada bırakma, tanımsız imha...) sessizce çizilmez; planlamaya geri bildirilir
    for bi, b in enumerate(sheet.get("beats", [])):
        if float(b.get("t_end", 0)) <= t0 or float(b.get("t_start", 0)) >= t1:
            continue
        for oi, ob in enumerate((b.get("choreo") or {}).get("objects", [])):
            for pr in object_state.validate(ob.get("track") or [], b.get("characters") or None, setpieces2d.TARGETS, setpieces2d.SINKS):
                bad.append(f"vuruş {b.get('id', bi)} nesne {oi} ({ob.get('prop')}): {pr}")
    if bad:
        return {"status": "BLOCKED", "error": "NESNE_IZI_GECERSIZ", "problems": bad}
    blender = find_blender() if engine != "2d" else "n/a"
    if not blender:
        return {"status": "BLOCKED", "error": "BLENDER_MISSING"}
    frames = os.path.join(rdir, "frames")
    started = time.time(); problems = []
    for si, (a, b, loc) in enumerate(split_by_scene(sheet, t0, t1)):
        plan = sp.plan(episode_dir, bible, assets, a, b)
        pp = os.path.join(rdir, f"plan_{si}.json")
        json.dump(plan, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
        if engine == "2d":
            designs = {}
            for ch in bible["characters"]:
                spp = os.path.join(assets, f"{ch['id']}.spec.json")
                designs[ch["id"]] = pp2.derive_design(ch, json.load(open(spp, encoding="utf-8")) if os.path.exists(spp) else {})
            hp = r2.handoff_problems(plan, designs)
            if hp:
                return {"status": "BLOCKED", "error": "EL_DEGISTIRME_ULASILAMAZ", "problems": problems + hp}
            stats = r2.render_window(plan, designs, frames)
            json.dump(stats, open(os.path.join(frames, "render_stats.json"), "w"))
            if stats.get("disk_blocked"):
                return {"status": "BLOCKED", "error": "DISK_YETERSIZ", "problems": problems + ["%s: boş disk %d MB, gereken ~%d MB; alan açılınca yeniden çalıştırın" % (loc, stats["disk_free_mb"], stats["disk_need_mb"])], "render_stats": stats}
            if stats.get("missing"):
                return {"status": "BLOCKED", "error": "FRAMES_MISSING", "problems": problems + ["%s: %d kare eksik/bozuk (işçi çökmesi/zaman aşımı/iptal); yeniden çalıştırınca eksikler tamamlanır" % (loc, stats["missing"])], "render_stats": stats}
            continue
        script = os.path.join(HERE, "studio_backends", "shot_render_blender.py")
        for eng in dict.fromkeys([engine, "eevee", "workbench"]):
            r = runner([blender, "-b", "--factory-startup", "-noaudio", "--python-exit-code", "1", "--python", script,
                        "--", "--plan", pp, "--out", frames, "--engine", eng, "--samples", str(samples)],
                       capture_output=True, text=True, timeout=6 * 3600)
            tail = (r.stdout + r.stderr)[-1500:]
            print(tail[-600:])
            if r.returncode == 0 and "RENDER_OK" in r.stdout:
                break
            problems.append(f"{loc} {eng}: {tail[-300:]}")
        else:
            return {"status": "BLOCKED", "error": "RENDER_FAILED", "problems": problems}
    pngs = sorted(glob.glob(os.path.join(frames, "f*.png")))
    if not pngs:
        return {"status": "BLOCKED", "error": "NO_FRAMES", "problems": problems}
    # ses: animatik zaman çizelgesi (satır ofsetleri düzeltilmiş)
    vm = os.path.join(episode_dir, "voice_manifest.json")
    wav = os.path.join(episode_dir, "animatic", "timeline.wav")
    if os.path.exists(vm):
        os.makedirs(os.path.dirname(wav), exist_ok=True)
        items = sp.assign_offsets(json.load(open(vm, encoding="utf-8"))["items"])
        wav = aw.build_timeline(episode_dir, items, sheet["beats"], float(sheet["beats"][-1]["t_end"]))
        try:  # müzik/efekt yatağı (yerel, telifsiz); başarısız olursa diyalog tek başına kalır
            import music_worker as mw
            if mw.needs_refresh(episode_dir):          # beat_sheet değiştiyse yatak (müzik + temas efektleri) yeniden üretilir; eski yatak körlemesine kullanılmaz
                mw.run(episode_dir, os.path.basename(os.path.dirname(os.path.abspath(episode_dir))) or "ahos")
            wav = mw.mix(episode_dir, wav)
        except Exception as e:  # noqa: BLE001
            problems.append(f"music: {e}")
    out = os.path.join(rdir, f"clip_{int(t0)}_{int(t1)}.mp4")
    FPS_ = int(os.environ.get("AHOS_FPS", "12"))
    f0 = int(round(t0 * FPS_))
    cmd = [shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS_), "-start_number", str(f0),
           "-i", os.path.join(frames, "f%05d.png")]
    if os.path.exists(wav):
        cmd += ["-ss", str(t0), "-i", wav]
    cmd += ["-t", str(t1 - t0), "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    if os.path.exists(wav):
        cmd += ["-af", _loud_filter(), "-strict", "-2", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "96k"]
    cmd += ["-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    st = {}
    shutil.rmtree(os.path.join(frames, "__none__"), ignore_errors=True)
    sp_ = os.path.join(frames, "render_stats.json")
    if os.path.exists(sp_):
        st = json.load(open(sp_))
    spf = st.get("sec_per_frame")
    est = round(spf * 480 * 12 / 3600, 1) if spf else None
    man = {"status": "PASSED", "clip": out, "frames": len(pngs), "sec_per_frame": spf, "engine": st.get("engine"),
           "estimate_hours_for_480s": est, "cost_eur": 0, "problems": problems,
           "note": "yerel render: para harcanmaz, süre harcanır"}
    json.dump(man, open(os.path.join(rdir, "render_manifest.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-dir", required=True); ap.add_argument("--series", required=True)
    ap.add_argument("--from", dest="t0", type=float, default=0.0); ap.add_argument("--to", dest="t1", type=float, default=10.0)
    ap.add_argument("--engine", default="2d", help="2d (varsayılan) | toon | eevee | workbench"); ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--fps", type=int, default=None, help="kare hızı (12 varsayılan, 24 akıcı)")
    a = ap.parse_args()
    if a.fps:
        os.environ["AHOS_FPS"] = str(a.fps)
    bible = json.load(open(a.series, encoding="utf-8"))
    m = run(a.episode_dir, bible, a.t0, a.t1, os.path.dirname(os.path.abspath(a.series)), a.engine, a.samples)
    print(json.dumps(m, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
