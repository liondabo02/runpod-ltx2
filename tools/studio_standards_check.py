#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AHOS 2D kalite standardı denetçisi: bölüm klasörü + bible + varlıklar üzerinde ÖLÇÜLEBİLİR kontroller (docs/2D_KALITE_STANDARDI.md).
Yaratıcı zevki ölçmez. Çıktı: <bölüm>/standards_report.json  (durum: PASS / NEEDS_WORK, her kapı için ölçüm + eşik).
python tools/studio_standards_check.py --series-id ahos-bizim-aile --episode e001"""
import argparse, itertools, json, os, sys, wave
import array
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)


def _jl(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def face_distinctness(bible, assets):
    keys = ["eye_shape", "brow_shape", "nose", "hair_style", "beard", "accessory", "lashes", "freckles", "earrings", "pregnant"]
    feats = {}
    for ch in bible["characters"]:
        sp = _jl(os.path.join(assets, ch["id"] + ".spec.json")) or {}
        f = {k: str(sp.get(k, "-")) for k in keys}
        for k in ("hair", "skin"):
            pal = (sp.get("palette") or {}).get(k)
            f[k] = tuple(round(v * 4) for v in pal) if pal else None
        f["face_w"] = round(float(sp.get("face_w", 1.0)) * 10); f["build"] = round(float(sp.get("build", 1.0)) * 10)
        feats[ch["id"]] = f
    worst, pairs = None, []
    for a, b in itertools.combinations(feats, 2):
        d = sum(1 for k in feats[a] if feats[a][k] != feats[b][k])
        pairs.append((d, a, b))
    pairs.sort()
    return {"min_pair_distance": pairs[0][0] if pairs else None, "closest_pairs": [f"{a}-{b}:{d}" for d, a, b in pairs[:5]]}


def wav_edges(path, thr_db=-38.0):
    with wave.open(path, "rb") as w:
        sr, n = w.getframerate(), w.getnframes(); d = array.array("h"); d.frombytes(w.readframes(n))
    if not d: return 0.0, 0.0, 0.0
    pk = max(abs(x) for x in d) or 1; thr = pk * (10 ** (thr_db / 20))
    first = next((i for i, x in enumerate(d) if abs(x) > thr), 0)
    last = len(d) - 1 - next((i for i, x in enumerate(reversed(d)) if abs(x) > thr), 0)
    return first / sr, (len(d) - 1 - last) / sr, n / sr


def check(series_id, episode):
    sdir = os.path.join(ROOT, "series", series_id); ep = os.path.join(sdir, "episodes", episode)
    bible = _jl(os.path.join(sdir, "series-bible.json")); assets = os.path.join(sdir, "assets")
    sheet = _jl(os.path.join(ep, "beat_sheet.json")); vm = _jl(os.path.join(ep, "voice_manifest.json")) or {"items": []}
    gates = []

    def gate(name, ok, measured, threshold):
        gates.append({"gate": name, "status": "PASS" if ok else "NEEDS_WORK", "measured": measured, "threshold": threshold})

    fd = face_distinctness(bible, assets)
    gate("yüz ayrışması", (fd["min_pair_distance"] or 0) >= 4, fd, ">= 4 özellik farkı (en yakın çift)")
    items = vm.get("items", [])
    ids = {(i.get("voice"), (_jl(os.path.join(ep, "voice_manifest.json")) or {}).get("x")) for i in items}
    chars_speaking = {i["char"] for i in items}
    pitch_ids = {c["id"]: (c.get("voice") or {}).get("pitch_hz") for c in bible["characters"] if c["id"] in chars_speaking}
    distinct = len({(pitch_ids[c], next((i["voice"] for i in items if i["char"] == c), None)) for c in pitch_ids})
    gate("ses kimliği", distinct >= 0.75 * max(1, len(chars_speaking)), {"konuşan": len(chars_speaking), "farklı ses/perde": distinct}, ">= %75 konuşan")
    lead_tail, gaps = [], []
    for it in items[:200]:
        p = os.path.join(ep, it["wav"].replace("\\", "/"))
        if os.path.exists(p):
            a, b, _ = wav_edges(p); lead_tail.append(max(a, b))
    by_beat = {}
    for it in items: by_beat.setdefault(it["beat"], []).append(it)
    for lst in by_beat.values():
        for x, y in zip(lst, lst[1:]):
            gaps.append(y.get("start_s", 0) - (x.get("start_s", 0) + x["duration_s"]))
    gate("satır başı/sonu sessizlik", bool(lead_tail) and max(lead_tail) <= 0.25, {"en_uzun_sn": round(max(lead_tail), 2) if lead_tail else None}, "<= 0.25 sn")
    gate("satır arası boşluk", (max(gaps) if gaps else 0) <= 0.8, {"en_uzun_sn": round(max(gaps), 2) if gaps else 0}, "<= 0.8 sn")
    # dudak senkronu: ilk ağız açılışı - ses başlangıcı
    diffs = []
    for it in items[:60]:
        p = os.path.join(ep, it["wav"].replace("\\", "/")); vj = os.path.join(ep, (it.get("visemes") or "").replace("\\", "/"))
        if os.path.exists(p) and os.path.exists(vj):
            cues = (_jl(vj) or {}).get("mouthCues", []); op = next((c["start"] for c in cues if c["value"] != "X"), None)
            if op is not None: diffs.append(abs(op - wav_edges(p)[0]))
    gate("dudak senkronu", bool(diffs) and sorted(diffs)[len(diffs) // 2] <= 0.08, {"ortanca_fark_sn": round(sorted(diffs)[len(diffs) // 2], 3) if diffs else None}, "<= 0.08 sn")
    bed = os.path.join(ep, "audio", "bed.wav"); mm = _jl(os.path.join(ep, "audio", "music_manifest.json"))
    gate("müzik yatağı", os.path.exists(bed) and bool(mm), {"bed": os.path.exists(bed)}, "var")
    # kurgu
    if sheet:
        durs = [float(b["t_end"]) - float(b["t_start"]) for b in sheet["beats"]]
        import math as _m                      # gerçek kesme: render2d uzun vuruşu (>5 sn) 3,5 sn'lik çekimlere böler
        cuts = sum((_m.ceil(d / 3.5) if d > 5.0 else 1) for d in durs)
        eff = sum(durs) / max(1, cuts)
        gate("kurgu: ortalama çekim (gerçek kesme)", eff <= 6.0, {"ortalama_sn": round(eff, 2), "vuruş_ort_sn": round(sum(durs) / len(durs), 2), "kesme_sayısı": cuts}, "<= 6 sn")
        enr = sum(1 for b in sheet["beats"] if (b.get("enrichment") or {}).get("added"))
        gate("senaryo zenginleştirme", enr >= 0.5 * len(sheet["beats"]), {"zenginleşen_çekim": enr, "toplam": len(sheet["beats"])}, ">= %50 çekim")
    fid = _jl(os.path.join(ep, "script_fidelity.json"))
    if fid: gate("senaryo sadakati", fid.get("coverage", 0) >= 0.85, {"kapsam": fid.get("coverage")}, ">= 0.85")
    rep = {"episode": episode, "status": "PASS" if all(g["status"] == "PASS" for g in gates) else "NEEDS_WORK", "gates": gates,
           "creative": "NOT_EVALUATED (zevk sahip tarafından onaylanır)"}
    json.dump(rep, open(os.path.join(ep, "standards_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--series-id", required=True); ap.add_argument("--episode", required=True)
    a = ap.parse_args(); r = check(a.series_id, a.episode)
    print("STANDART:", r["status"])
    for g in r["gates"]: print(" -", g["status"], g["gate"], json.dumps(g["measured"], ensure_ascii=False)[:110])
