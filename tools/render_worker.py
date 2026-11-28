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
import shot_motion as sm  # noqa: E402
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


import worker_events  # noqa: E402


def run(episode_dir, bible, t0, t1, series_dir, engine="2d", samples=16, runner=subprocess.run):
    episode_dir = os.path.abspath(episode_dir)
    assets = os.path.join(series_dir, "assets")
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    rdir = os.path.join(episode_dir, "render"); os.makedirs(rdir, exist_ok=True)
    import episode_length                                # süre kapısı: dizinin istediği en az süreden kısa plan TAM BÖLÜM olarak render edilmez
    _len = episode_length.check(sheet, bible, t0, t1)
    json.dump(_len, open(os.path.join(rdir, "episode_length_gate.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if _len["problems"]:
        return {"status": "BLOCKED", "error": "BOLUM_COK_KISA", "problems": episode_length.messages(_len)}
    import dialogue_check                                # diyalog kapısı (planlayıcıdan önce): senaryodaki replik eksik/eski/bozuksa film üretilmez
    _dlg = dialogue_check.check(episode_dir, bible, t0, t1, allow_estimated=os.environ.get("AHOS_ALLOW_ESTIMATED_VOICE") == "1", sheet=sheet)
    json.dump(_dlg, open(os.path.join(rdir, "dialogue_gate.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if _dlg["problems"]:
        return {"status": "BLOCKED", "error": "DIYALOG_EKSIK_VEYA_HATALI", "problems": dialogue_check.messages(_dlg)}
    import action_trace                                  # izlenebilirlik kapısı: storyboard'un/metnin istediği eylem üretim verisinde yoksa sessizce çizilmez
    _trace = action_trace.check(sheet, series_dir, t0, t1)
    json.dump(_trace, open(os.path.join(rdir, "action_trace.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if _trace["problems"]:
        return {"status": "BLOCKED", "error": "EYLEM_VERIYE_BAGLANMAMIS", "problems": action_trace.messages(_trace)}
    import object_state, setpieces2d
    _H = {cid: d["height"] for cid, d in pp2.designs_for(bible, assets).items()}      # çizilen boy (planlayıcıyla aynı kaynak)
    locs_ = setpieces2d.load_locations(series_dir)
    bad = []                                            # ön kontrol: geçersiz nesne izi (ışınlanma, havada bırakma, tanımsız imha...) sessizce çizilmez; planlamaya geri bildirilir
    for bi, b in enumerate(sheet.get("beats", [])):
        if float(b.get("t_end", 0)) <= t0 or float(b.get("t_start", 0)) >= t1:
            continue
        tg_, sk_ = setpieces2d.anchors_for(setpieces2d.pieces_of(locs_.get(b.get("location") or "", {})))       # hedefler mekân verisinden (motor sabiti değil)
        for oi, ob in enumerate((b.get("choreo") or {}).get("objects", [])):
            for pr in object_state.validate(ob.get("track") or [], b.get("characters") or None, tg_, sk_):
                bad.append(f"vuruş {b.get('id', bi)} nesne {oi} ({ob.get('prop')}): {pr}")
    if not bad:                                          # atış okunabilirliği: çizimle AYNI konum kaynağından (planlayıcı + süreklilik + yerleşim), ayrı tahmin yok
        for pb in sp.plan(episode_dir, bible, assets, t0, t1)["beats"]:
            dur_ = pb["t_end"] - pb["t_start"]
            def hx(cid, t_, _b=pb, _d=dur_):
                return sm.motion_x(_b["motion"][cid], t_, _d, _H[cid]) if cid in _b["motion"] else 0.0
            for ob in pb["choreo"]["objects"]:
                for pr in object_state.throw_problems(ob.get("track") or [], hx, pb["targets"]):
                    bad.append(f"vuruş {pb['i']} nesne {ob.get('prop')}: {pr}")
    if bad:
        return {"status": "BLOCKED", "error": "NESNE_IZI_GECERSIZ", "problems": bad}
    import scene_contract as sc                          # sahne sözleşmesi kapısı: tutarsız süreklilik/yerleşim render'a girmez, sorumlu motor adıyla geri döner
    _plan = sp.plan(episode_dir, bible, assets, t0, t1)
    _c = sc.from_beat_sheet(sheet, _plan, project_id=bible.get("id", "series"), episode_id=os.path.basename(episode_dir), window=(t0, t1),
                            characters={c["id"]: c for c in bible.get("characters", [])})
    _blk, _warn = sc.gate(_c)
    json.dump({"blocking": _blk, "warnings": _warn}, open(os.path.join(rdir, "contract_gate.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if _blk:
        return {"status": "BLOCKED", "error": "SAHNE_SOZLESMESI_TUTARSIZ",
                "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in _blk]}
    if engine == "2d":                                   # yüz kapısı: planda oynayan her tasarımda göz ve kaş çizilen pikselden ölçülür
        import face_visibility
        _faces = face_visibility.check_designs(pp2.designs_for(bible, assets), {c for b_ in _plan["beats"] for c in b_["cast"]})
        json.dump({"characters": _faces, "thresholds": face_visibility.MIN_VISIBLE}, open(os.path.join(rdir, "face_visibility.json"), "w", encoding="utf-8"), ensure_ascii=False)
        _hidden = face_visibility.problems(_faces)
        if _hidden:
            return {"status": "BLOCKED", "error": "YUZ_OKUNAMIYOR",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['character']}: {x['why']}" for x in _hidden]}
    if engine == "2d":                                   # okunabilirlik kapısı: temas anları çizilen katmanlardan ölçülür; okunmayan aksiyon üretime girmez
        import readability
        _rep = readability.measure_plan(_plan, pp2.designs_for(bible, assets))
        json.dump({"events": _rep, "thresholds": readability.DEFAULTS}, open(os.path.join(rdir, "readability.json"), "w", encoding="utf-8"), ensure_ascii=False)
        _unread = readability.problems(_rep)
        if _unread:
            return {"status": "BLOCKED", "error": "AKSIYON_OKUNAMIYOR",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in _unread]}
    if engine == "2d":                                   # bloklama kapısı: temassız anlarda bir oyuncu diğerini uzun süre büyük ölçüde kapatamaz
        _occ = readability.measure_occlusion(_plan, pp2.designs_for(bible, assets))
        json.dump({"occluded": _occ, "thresholds": {k: v for k, v in readability.DEFAULTS.items() if k.startswith("occl_")}},
                  open(os.path.join(rdir, "occlusion.json"), "w", encoding="utf-8"), ensure_ascii=False)
        if _occ:
            return {"status": "BLOCKED", "error": "OYUNCU_ORTULUYOR",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in readability.occlusion_problems(_occ)]}
    if engine == "2d":                                   # kadraj kapısı: alt kenar bacak ortasından ya da yakın planda tutulan konu nesnesinden geçemez
        _crop = readability.measure_crop(_plan, pp2.designs_for(bible, assets))
        json.dump(dict(_crop, thresholds={k: v for k, v in readability.DEFAULTS.items() if k.startswith("crop_")}),
                  open(os.path.join(rdir, "framing_crop.json"), "w", encoding="utf-8"), ensure_ascii=False)
        if _crop["violations"]:
            return {"status": "BLOCKED", "error": "KADRAJ_ALTTAN_KESIK",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in readability.crop_problems(_crop)]}
    if engine == "2d":                                   # gösterme kapısı: gösterilen hedef jest boyunca görünür ve kol ona bakar
        import readability
        _pts = readability.measure_pointing(_plan, pp2.designs_for(bible, assets))
        json.dump({"gestures": _pts, "thresholds": {k: v for k, v in readability.DEFAULTS.items() if k.startswith("point_")}},
                  open(os.path.join(rdir, "pointing.json"), "w", encoding="utf-8"), ensure_ascii=False)
        _lost = readability.pointing_problems(_pts)
        if _lost:
            return {"status": "BLOCKED", "error": "JEST_HEDEFI_OKUNAMIYOR",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in _lost]}
    if engine == "2d":                                   # tepki planı kapısı: kamera dinleyene kesiyorsa tepki çizilen yüzde görünmeli ve plan göz yakalayacak kadar sürmeli
        import readability
        _shots = readability.reaction_shots(_plan, pp2.designs_for(bible, assets))
        json.dump({"shots": _shots, "thresholds": {k: v for k, v in readability.DEFAULTS.items() if k.startswith("react_")}},
                  open(os.path.join(rdir, "reaction_shots.json"), "w", encoding="utf-8"), ensure_ascii=False)
        _empty = readability.reaction_problems(_shots)
        if _empty:
            return {"status": "BLOCKED", "error": "TEPKI_PLANI_BOS",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in _empty]}
    if engine == "2d":                                   # kamera kapısı: kadraj tek karede atlayamaz; her kesme gerçek kesme eşiğini geçer ya da sürekli harekettir
        import readability
        _pops = readability.camera_pops(_plan, pp2.designs_for(bible, assets))
        json.dump({"pops": _pops, "thresholds": {k: v for k, v in readability.DEFAULTS.items() if k.startswith(("pop_", "cut_"))}},
                  open(os.path.join(rdir, "camera_pops.json"), "w", encoding="utf-8"), ensure_ascii=False)
        _jump = readability.camera_pop_problems(_pops)
        if _jump:
            return {"status": "BLOCKED", "error": "KAMERA_ATLAMASI",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in _jump]}
    if engine == "2d":                                   # kurgu kapısı: katmanların birleşimi göz yakalayamayacak kadar kısa plan bırakamaz
        import readability
        _short = readability.short_shots(_plan, pp2.designs_for(bible, assets))
        json.dump({"short_shots": _short}, open(os.path.join(rdir, "short_shots.json"), "w", encoding="utf-8"), ensure_ascii=False)
        if _short:
            return {"status": "BLOCKED", "error": "ANLIK_PLAN",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in readability.short_shot_problems(_short)]}
    if engine == "2d":                                   # poz kapısı: oyuncunun eli/kolu/başı/ayağı tek karede ışınlanamaz (görünüş değişimi ayrı kusur, durdurmaz)
        import readability
        _jumps = readability.pose_jumps(_plan, pp2.designs_for(bible, assets))
        json.dump({"jumps": _jumps, "thresholds": {k: v for k, v in readability.DEFAULTS.items() if k.startswith("jump_")}},
                  open(os.path.join(rdir, "pose_jumps.json"), "w", encoding="utf-8"), ensure_ascii=False)
        _ojumps = readability.object_jumps(_plan, pp2.designs_for(bible, assets))
        json.dump({"jumps": _ojumps, "thresholds": {k: v for k, v in readability.DEFAULTS.items() if k.startswith(("obj_", "jump_"))}},
                  open(os.path.join(rdir, "object_jumps.json"), "w", encoding="utf-8"), ensure_ascii=False)
        if _ojumps:
            return {"status": "BLOCKED", "error": "NESNE_SICRAMASI",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in readability.object_jump_problems(_ojumps)]}
        if readability.pose_jump_problems(_jumps):
            return {"status": "BLOCKED", "error": "POZ_SICRAMASI",
                    "problems": [f"[{x['engine']}] {x['rule']} {x['shot']}: {x['why']}" for x in readability.pose_jump_problems(_jumps)]}
    blender = find_blender() if engine != "2d" else "n/a"
    if not blender:
        return {"status": "BLOCKED", "error": "BLENDER_MISSING"}
    frames = os.path.join(rdir, "frames")
    started = time.time(); problems = []
    for si, (a, b, loc) in enumerate(split_by_scene(sheet, t0, t1)):
        worker_events.note("%d. sahneyi çiziyor (%s, %.0f-%.0f sn)" % (si + 1, loc, a, b))
        plan = sp.plan(episode_dir, bible, assets, a, b)
        pp = os.path.join(rdir, f"plan_{si}.json")
        json.dump(plan, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
        if engine == "2d":
            designs = pp2.designs_for(bible, assets)
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
           "voice": _dlg["voice"], "draft": _dlg["voice"] == "estimated",           # tahmini süreli sesle çizilen klip taslaktır, teslim değildir
           "untraced_beats": _trace["untraced_beats"],       # eylem metni hiçbir veriyle denetlenmeyen vuruşlar ('geçti' değil, 'denetlenmedi')
           "note": "yerel render: para harcanmaz, süre harcanır"}
    json.dump(man, open(os.path.join(rdir, "render_manifest.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return man


def _probe_seconds(path):
    """Klibin gerçek süresi (ffprobe); okunamazsa None."""
    try:
        r = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return None


def run_chunked(episode_dir, bible, t0, t1, series_dir, chunk_s=30.0, engine="2d", samples=16, free_bytes=None, runner=run):
    """Parça parça üretim: pencereyi chunk_s'lik parçalara böler; her parça kendi klibine kodlanır ve süresi DOĞRULANIR.
    Disk, tüm pencerenin kareleri için yetmiyorsa, yalnız BU işin ürettiği ve kodlanıp doğrulanmış parçanın kareleri silinir
    (başka işlerin/kullanıcının dosyalarına dokunulmaz); yetiyorsa hiçbir şey silinmez. Parçalar -c copy ile birleştirilir. Çökmede mevcut doğrulanmış parçalar, GİRDİLERİ DEĞİŞMEDİYSE (clip_cache) yeniden üretilmez."""
    rdir = os.path.join(episode_dir, "render"); os.makedirs(rdir, exist_ok=True)
    fps = int(os.environ.get("AHOS_FPS", "12")); per_frame = 1.0e6
    free = free_bytes if free_bytes is not None else shutil.disk_usage(rdir).free
    total_need = (t1 - t0) * fps * per_frame * 1.3
    purge = total_need > free
    edges = []; a = t0
    while a < t1 - 1e-6:
        edges.append((a, min(t1, a + chunk_s))); a += chunk_s
    parts = []; log = []; draft = False
    import clip_cache
    for (a, b) in edges:
        clip = os.path.join(rdir, f"clip_{int(a)}_{int(b)}.mp4")
        inputs = clip_cache.fingerprint(episode_dir, bible, series_dir, a, b, fps, engine, samples)      # üretimden ÖNCE: üretim sırasında değişen girdi sonraki koşuda yakalanır
        ok, rec = clip_cache.reusable(clip, inputs)
        dur = _probe_seconds(clip) if ok else None
        if dur is not None and abs(dur - (b - a)) <= 0.25:               # doğrulanmış VE aynı girdili parça: yeniden üretme (devam/yeniden başlatma)
            draft = draft or bool(rec.get("draft"))
            parts.append(clip); log.append({"chunk": [a, b], "status": "REUSED", "seconds": dur}); continue
        remade = None if not os.path.exists(clip) else (rec if not ok else "klip süresi tutmuyor")
        clip_cache.forget(clip)
        m = runner(episode_dir, bible, a, b, series_dir, engine, samples)
        if m.get("status") != "PASSED":
            return {"status": "BLOCKED", "error": m.get("error", "CHUNK_FAILED"), "chunk": [a, b], "problems": m.get("problems", []), "parts_done": log}
        dur = _probe_seconds(m["clip"])
        if dur is None or abs(dur - (b - a)) > 0.25:
            return {"status": "BLOCKED", "error": "CHUNK_SURE_UYUSMAZ", "chunk": [a, b], "problems": [f"klip {dur} sn, beklenen {b - a:.2f} sn"], "parts_done": log}
        parts.append(m["clip"]); freed = 0
        clip_cache.record(m["clip"], inputs, m.get("draft", False)); draft = draft or bool(m.get("draft"))
        if purge:
            fdir = os.path.join(rdir, "frames")
            for i in range(int(round(a * fps)), int(round(b * fps)) + 1):
                fp = os.path.join(fdir, f"f{i:05d}.png")
                if os.path.exists(fp):
                    freed += os.path.getsize(fp); os.remove(fp)
        log.append({"chunk": [a, b], "status": "DONE", "seconds": dur, "freed_mb": round(freed / 1e6), **({"remade_because": remade} if remade else {})})
    lst = os.path.join(rdir, "concat.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % p_.replace("\\", "/") for p_ in parts))
    out = os.path.join(rdir, f"episode_{int(t0)}_{int(t1)}.mp4")
    if len(parts) == 1:
        shutil.copyfile(parts[0], out)
    else:
        subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    dur = _probe_seconds(out)
    if dur is None or abs(dur - (t1 - t0)) > 0.5 + 0.05 * len(parts):
        return {"status": "BLOCKED", "error": "BIRLESTIRME_SURE_UYUSMAZ", "problems": [f"birleşik {dur} sn, beklenen {t1 - t0:.1f} sn"], "parts_done": log}
    return {"status": "PASSED", "clip": out, "seconds": dur, "chunks": log, "purge_mode": purge, "draft": draft, "cost_eur": 0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-dir", required=True); ap.add_argument("--series", required=True)
    ap.add_argument("--from", dest="t0", type=float, default=0.0); ap.add_argument("--to", dest="t1", type=float, default=10.0)
    ap.add_argument("--engine", default="2d", help="2d (varsayılan) | toon | eevee | workbench"); ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--fps", type=int, default=None, help="kare hızı (12 varsayılan, 24 akıcı)")
    ap.add_argument("--draft-voice", action="store_true", help="yalnız taslak: tahmini süre işaretli ses listesiyle çiz (manifest 'draft': true)")
    ap.add_argument("--chunk-s", type=float, default=0.0, help="parça parça üretim (sn); disk sınırlıysa kullanın")
    a = ap.parse_args()
    if a.fps:
        os.environ["AHOS_FPS"] = str(a.fps)
    if a.draft_voice:
        os.environ["AHOS_ALLOW_ESTIMATED_VOICE"] = "1"
    bible = json.load(open(a.series, encoding="utf-8"))
    sd = os.path.dirname(os.path.abspath(a.series))
    m = run_chunked(a.episode_dir, bible, a.t0, a.t1, sd, a.chunk_s, a.engine, a.samples) if a.chunk_s > 0 else run(a.episode_dir, bible, a.t0, a.t1, sd, a.engine, a.samples)
    print(json.dumps(m, ensure_ascii=False, indent=2))
    return exit_code(m)


def exit_code(manifest):
    """Yalnız PASSED başarıdır; engel/eksik sonuç çağırana sıfır olmayan kodla bildirilir."""
    return 0 if (manifest or {}).get("status") == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
