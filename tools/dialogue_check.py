#!/usr/bin/env python3
"""AHOS diyalog kapsama denetimi (diziden bağımsız): senaryodaki her replik üretime girecek ses listesinde var mı?

Kaynak beat_sheet'in 'dialogue' alanıdır; ses işçisiyle AYNI ayrıştırıcı (voice_worker.parse_dialogue) kullanılır.
'dialogue' alanı hiç olmayan vuruş denetlenmez (rapora 'unchecked_beats' olarak yazılır); alan boşsa o vuruşta replik OLMAMALIDIR.

Gerçek ses yokken yalnız TASLAK için açıkça 'tahmini süre' işaretli liste üretilebilir:
  python tools/dialogue_check.py --episode-dir <bölüm> --series <series-bible.json> --write-estimate
Tahmini liste ses değildir; render kapısı açık taslak izni (AHOS_ALLOW_ESTIMATED_VOICE=1 / --draft-voice) olmadan üretime sokmaz.
Süre tahmini kalite kuralı değildir; katsayılar proje verisinden (bible['speech_estimate']) değiştirilebilir."""
import argparse
import collections
import json
import os
import re
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import voice_worker as vw  # noqa: E402

ESTIMATE = {"base_s": 0.5, "per_char_s": 0.065, "gap_s": 0.3, "lead_s": 0.2}
FIT_SLACK_S = 0.05          # repliğin vuruş sonunu aşabileceği yuvarlama payı
DURATION_SLACK_S = 0.15     # listedeki süre ile ses dosyasının süresi arasındaki en büyük fark
_VOICE_LANG = re.compile(r"^([a-z]{2,3})[-_][A-Z]{2}-")      # 'tr-TR-AhmetNeural', 'de_DE-thorsten-medium'


def _norm(text):
    return " ".join(str(text or "").split())


def episode_language(episode_dir, sheet, bible):
    """Bu bölüm kopyasının dili: sayfadaki 'language'; yoksa lang/<kod>/ klasör adı; yoksa dizinin ana dili."""
    d = os.path.abspath(episode_dir)
    folder = os.path.basename(d) if os.path.basename(os.path.dirname(d)) == "lang" else None
    return sheet.get("language") or folder or bible.get("language_default") or "tr"


def expected_lines(sheet, bible):
    """({vuruş: [(konuşan, metin)]}, [ayrıştırılamayan vuruşlar], [alanı olmayan vuruşlar])."""
    chars = {c["id"]: c for c in bible.get("characters", [])}
    out, unparsed, absent = {}, [], []
    for i, b in enumerate(sheet.get("beats", [])):
        if "dialogue" not in b:
            absent.append(i)
            continue
        raw = b.get("dialogue")
        if raw is not None and not isinstance(raw, str):
            unparsed.append(i)
            continue
        got = [(c, t) for c, t in vw.parse_dialogue(raw, b.get("characters") or None, chars) if c in chars]
        if _norm(raw) and not got:
            unparsed.append(i)
        out[i] = got
    return out, unparsed, absent


def estimate_manifest(sheet, bible, lang="tr"):
    k = dict(ESTIMATE, **(bible.get("speech_estimate") or {}))
    lines, unparsed, _absent = expected_lines(sheet, bible)
    if unparsed:
        raise ValueError(f"diyalog alanı ayrıştırılamayan vuruşlar: {unparsed}")
    items = [{"beat": i, "char": c, "text": t, "duration_s": round(k["base_s"] + k["per_char_s"] * len(_norm(t)), 2), "timing": "estimated"}
             for i in sorted(lines) for c, t in lines[i]]
    return {"stage": "voice-estimate", "status": "ESTIMATED", "lang": lang, "lines": len(items), "items": items,
            "note": "TAHMİNİ SÜRE: ses dosyası yoktur; yalnız taslak/animatik içindir, teslim edilemez"}


def write_estimate(episode_dir, bible):
    """Tahmini listeyi yazar. Gerçek (tahmini olmayan) bir ses listesinin üzerine ASLA yazmaz."""
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    path = os.path.join(episode_dir, "voice_manifest.json")
    if os.path.exists(path):
        old = json.load(open(path, encoding="utf-8"))
        if old.get("status") != "ESTIMATED":
            raise FileExistsError("voice_manifest.json gerçek bir ses listesi; üzerine yazılmadı")
    man = estimate_manifest(sheet, bible, episode_language(episode_dir, sheet, bible))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    return man


def _wav_seconds(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate()) if len(w.readframes(w.getnframes())) == w.getnframes() * w.getnchannels() * w.getsampwidth() else None
    except Exception:  # noqa: BLE001
        return None


def check(episode_dir, bible, t0=0.0, t1=float("inf"), allow_estimated=False, sheet=None):
    """Penceredeki vuruşlar için {'problems': [{'rule','beat','why'}], 'expected': n, 'matched': n, 'voice': 'none'|'files'|'estimated',
    'language': kod, 'unchecked_beats': [...]}."""
    if sheet is None:
        sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    beats = sheet.get("beats", [])
    window = {i for i, b in enumerate(beats) if float(b.get("t_end", 0)) > t0 and float(b.get("t_start", 0)) < t1}
    lines, unparsed, absent = expected_lines(sheet, bible)
    lang = episode_language(episode_dir, sheet, bible)
    problems = []

    def bad(rule, beat, why):
        problems.append({"rule": rule, "beat": beat, "why": why})
    for i in sorted(window & set(unparsed)):
        bad("DIYALOG_AYRISTIRILAMADI", i, "'dialogue' alanında metin var ama konuşanı belli replik çıkmıyor")
    for i in sorted(window & set(sheet.get("untranslated_beats") or [])):
        bad("CEVRILMEMIS_REPLIK", i, f"çevirisi olmayan replik kaynak dilde kaldı ('{lang}' sesiyle okunurdu)")
    n_expected = sum(len(lines.get(i, [])) for i in window)
    out = {"problems": problems, "expected": n_expected, "matched": 0, "voice": "none", "language": lang,
           "unchecked_beats": sorted(window & set(absent))}
    path = os.path.join(episode_dir, "voice_manifest.json")
    if not os.path.exists(path):
        if n_expected:
            bad("SES_LISTESI_YOK", None, f"senaryoda {n_expected} replik var, voice_manifest.json yok: film sessiz üretilirdi")
        return out
    try:
        man = json.load(open(path, encoding="utf-8"))
        items = [dict(it, beat=int(it["beat"]), duration_s=float(it["duration_s"]), char=str(it["char"])) for it in man["items"]]
    except Exception as e:  # noqa: BLE001
        bad("SES_LISTESI_BOZUK", None, f"voice_manifest.json okunamadı: {type(e).__name__}: {str(e)[:100]}")
        return out
    for it in items:
        if not 0 <= it["beat"] < len(beats):
            bad("REPLIK_FAZLA", it["beat"], f"{it['char']}: listede senaryoda olmayan vuruşa ait replik")
    mine = [it for it in items if it["beat"] in window]
    estimated = [it for it in mine if man.get("status") == "ESTIMATED" or it.get("timing") == "estimated"]
    out["voice"] = "estimated" if estimated else "files" if mine else "none"
    if estimated and not allow_estimated:
        bad("TAHMINI_SES", None, f"{len(estimated)} repliğin süresi tahmini, ses dosyası yok: yalnız açık taslak izniyle (--draft-voice) çizilir")
    if man.get("lang") and man["lang"] != lang:
        bad("YANLIS_DIL_SESI", None, f"ses listesinin dili '{man['lang']}', bölüm kopyasının dili '{lang}'")
    checked = window - set(absent) - set(unparsed)
    left = {i: collections.Counter((c, _norm(t)) for c, t in lines.get(i, [])) for i in checked}
    for it in mine:
        if it["beat"] not in checked:
            continue
        key = (it["char"], _norm(it.get("text")))
        if left[it["beat"]][key] > 0:
            left[it["beat"]][key] -= 1
            out["matched"] += 1
        else:
            bad("REPLIK_FAZLA", it["beat"], f"{it['char']}: \"{_norm(it.get('text'))[:60]}\" senaryoda yok (eski liste, yanlış konuşan ya da mükerrer)")
    for i in sorted(checked):
        for (c, t), n in left[i].items():
            for _ in range(n):
                bad("REPLIK_EKSIK", i, f"{c}: \"{t[:60]}\" ses listesinde yok")
    # repliğin vuruşa sığması: planlayıcıyla aynı yerleştirme kuralı (shot_planner.assign_offsets)
    import shot_planner as sp
    for it in sp.assign_offsets([dict(x) for x in mine]):
        if it["beat"] not in checked:
            continue
        b = beats[it["beat"]]
        end, dur = float(it["start_s"]) + it["duration_s"], float(b["t_end"]) - float(b["t_start"])
        if it["duration_s"] <= 0 or end > dur + FIT_SLACK_S:
            bad("REPLIK_SIGMIYOR", it["beat"], f"{it['char']}: replik {it['start_s']:.2f}-{end:.2f} sn, vuruş {dur:.2f} sn: sonu kesilir")
    for it in mine:
        if it["beat"] not in checked:
            continue
        m = _VOICE_LANG.match(str(it.get("voice") or ""))
        if m and m.group(1) != lang:
            bad("YANLIS_DIL_SESI", it["beat"], f"{it['char']}: ses '{it['voice']}', bölüm dili '{lang}'")
        if it in estimated or man.get("status") == "ESTIMATED" or it.get("timing") == "estimated":
            continue
        wav = str(it.get("wav") or "").replace("\\", "/")
        full = os.path.join(episode_dir, wav)
        if not wav or not os.path.isfile(full):
            bad("SES_DOSYASI_YOK", it["beat"], f"{it['char']}: ses dosyası yok ({wav or 'yol yazılmamış'})")
            continue
        if it.get("sha256") and vw.sha(full) != it["sha256"]:
            bad("SES_DOSYASI_DEGISMIS", it["beat"], f"{it['char']}: {wav} listedeki özetle uyuşmuyor (bozuk ya da eski dosya)")
            continue
        secs = _wav_seconds(full)
        if secs is None:
            bad("SES_DOSYASI_BOZUK", it["beat"], f"{it['char']}: {wav} tam okunamıyor")
        elif abs(secs - it["duration_s"]) > DURATION_SLACK_S:
            bad("SES_SURESI_UYUSMUYOR", it["beat"], f"{it['char']}: dosya {secs:.2f} sn, listede {it['duration_s']:.2f} sn")
    return out


def messages(report):
    return [f"[voice] {p['rule']} vuruş {'-' if p['beat'] is None else p['beat']}: {p['why']}" for p in report["problems"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-dir", required=True); ap.add_argument("--series", required=True)
    ap.add_argument("--write-estimate", action="store_true", help="tahmini süre işaretli taslak listesi yaz (gerçek listenin üzerine yazmaz)")
    a = ap.parse_args()
    bible = json.load(open(a.series, encoding="utf-8"))
    if a.write_estimate:
        try:
            man = write_estimate(a.episode_dir, bible)
        except (FileExistsError, ValueError) as e:
            print(f"YAZILMADI: {e}")
            return 2
        print(f"tahmini ses listesi yazıldı: {man['lines']} replik (TASLAK)")
        return 0
    rep = check(a.episode_dir, bible)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 2 if rep["problems"] else 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):                    # yönlendirilmiş cp1254 konsolda Türkçe karakter çökertmesin
        try:
            _s.reconfigure(errors="replace")
        except Exception:  # noqa: BLE001
            pass
    sys.exit(main())
