#!/usr/bin/env python3
"""AHOS Yerelleştirme (Dublaj) işçisi — diziden ve dilden bağımsız.

Bir bölümün diyaloglarını hedef dillere çevirir (LLM), her satırı orijinal satırın süresine sığdırır
(uzunsa kısaltma turu), o dilin sesleriyle seslendirir, o dilin ağız şekillerini üretir ve her dil için ayrı bir
çalışma klasörü (episodes/eNNN/lang/<kod>/) hazırlar. Görüntü render'ı o klasörden yapılır (ağız o dile uyar).

Kullanım: python tools/localisation_worker.py --episode-dir out/test003 --series series/x/series-bible.json --langs en,de
"""
import argparse, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import writers_room as wr  # noqa: E402
import voice_worker as vw  # noqa: E402

SYS = ("Sen profesyonel bir çizgi film DUBLAJ çevirmenisin. Çocuk dizisi diyaloglarını hedef dile çevir. Kurallar: "
       "doğal, konuşma dilinde, çocuğa uygun; her satır ORİJİNALİNDEN UZUN OLMASIN (ağız süresine sığmalı); "
       "karakter kimliklerini (char) AYNEN koru; özel adları (karakter adları) çevirme; kelimesi kelimesine değil, "
       "o dilde bir çocuğun söyleyeceği gibi çevir. SADECE JSON döndür: "
       '{"lines":[{"i":0,"text":"..."}]}')


def source_lines(sheet, chars):
    out = []
    for bi, b in enumerate(sheet["beats"]):
        for li, (cid, text) in enumerate(vw.parse_dialogue(b.get("dialogue"), b.get("characters") or None, chars)):
            if cid in chars:
                out.append({"beat": bi, "li": li, "char": cid, "text": text})
    return out


def _ask(llm, lang_name, items):
    """items: [{'char','text','max_chars'}]; yerel numara 0..n-1. Döner: {yerel_i: metin}"""
    user = "Hedef dil: %s\nSatırlar (i, konuşan, metin, en fazla karakter):\n" % lang_name + json.dumps(
        [dict(i=k, **it) for k, it in enumerate(items)], ensure_ascii=False)
    got = {}
    try:
        data = llm(SYS, user, temperature=0.4, need=["lines"])
    except Exception:
        return got
    arr = [x for x in data.get("lines", []) if isinstance(x, dict) and str(x.get("text", "")).strip()]
    for x in arr:
        try:
            k = int(x.get("i"))
        except (TypeError, ValueError):
            continue
        if 0 <= k < len(items):
            got[k] = str(x["text"]).strip()
    if len(got) < len(items) and len(arr) == len(items):      # numaralar bozuk ama sıra tam: sıraya göre eşle
        got = {k: str(x["text"]).strip() for k, x in enumerate(arr)}
    return got


def translate(lines, lang_name, budgets, llm=None, chunk=8):
    llm = llm or wr.llm_json
    res = {}
    for s in range(0, len(lines), chunk):
        part = lines[s:s + chunk]
        items = [{"char": l["char"], "text": l["text"], "max_chars": budgets[s + k]} for k, l in enumerate(part)]
        got = _ask(llm, lang_name, items)
        for _try in range(2):                                   # eksikleri tek tek tekrar dene
            miss = [k for k in range(len(part)) if k not in got]
            if not miss:
                break
            for k in miss:
                one = _ask(llm, lang_name, [items[k]])
                if 0 in one:
                    got[k] = one[0]
        for k, t in got.items():
            res[s + k] = t
    return res


def char_budget(orig_text, factor=1.25):
    return max(12, int(len(orig_text) * factor) + 6)


def build_lang_dir(episode_dir, bible, code, lang_info, llm=None, tts=vw.tts_real, visemes=vw.visemes_real, shorten_rounds=2):
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    chars = {c["id"]: c for c in bible["characters"]}
    lines = source_lines(sheet, chars)
    budgets = [char_budget(l["text"]) for l in lines]
    tr = translate(lines, lang_info.get("name", code), budgets, llm)
    for _ in range(shorten_rounds):                       # fazla uzun satırları kısalt
        long = [i for i, t in tr.items() if len(t) > budgets[i] * 1.15]
        if not long:
            break
        sub = [dict(lines[i], text=tr[i]) for i in long]
        fix = translate(sub, lang_info.get("name", code), [budgets[i] for i in long], llm, chunk=len(sub) or 1)
        for k, i in enumerate(long):
            if k in fix:
                tr[i] = fix[k]
    ldir = os.path.join(episode_dir, "lang", code)
    os.makedirs(ldir, exist_ok=True)
    out = json.loads(json.dumps(sheet))
    per_beat = {}
    for i, l in enumerate(lines):
        per_beat.setdefault(l["beat"], []).append("%s: %s" % (l["char"], tr.get(i, l["text"])))
    for bi, b in enumerate(out["beats"]):
        if bi in per_beat:
            b["dialogue"] = " | ".join(per_beat[bi])
    json.dump(out, open(os.path.join(ldir, "beat_sheet.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if lang_info.get("tts") == "mms":
        import tts_mms
        if tts_mms.available():
            mid = lang_info["mms_model"]
            tts = lambda text, voice, rate, pitch, out_wav, _m=mid: tts_mms.synth(text, _m, out_wav)  # noqa: E731
        else:
            lang_info = dict(lang_info, tts="none", tts_note="torch/transformers kurulu değil (tts_mms.py başlığına bak)")
    if lang_info.get("tts") == "none":   # bu dil için ses motoru bağlı değil: Türkçe sesle okutma, dürüstçe sadece metin
        missing = [i for i in range(len(lines)) if i not in tr]
        rep = {"lang": code, "status": "TEXT_ONLY" if not missing else "NEEDS_REVISION", "lines": len(lines), "untranslated": missing,
               "voice_problems": [lang_info.get("tts_note", "ses motoru yok")], "dir": ldir, "licence_status": None}
        if lang_info.get("native_review_required"):
            rep["native_review_required"] = True
            rep["quality_note"] = lang_info.get("quality_note", "anadili konuşan biri okumalı")
            if rep["status"] == "TEXT_ONLY":
                rep["status"] = "REVIEW_REQUIRED"
        json.dump(rep, open(os.path.join(ldir, "localisation_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return rep
    man = vw.run(ldir, bible, tts=tts, visemes=visemes, lang=code)
    missing = [i for i in range(len(lines)) if i not in tr]
    rep = {"lang": code, "status": man["status"] if not missing else "NEEDS_REVISION", "lines": len(lines), "untranslated": missing,
           "voice_problems": man["problems"], "dir": ldir, "licence_status": man.get("licence_status")}
    if lang_info.get("native_review_required"):
        rep["native_review_required"] = True
        rep["quality_note"] = lang_info.get("quality_note", "anadili konuşan biri okumalı")
        if rep["status"] in ("PASSED", "TEXT_ONLY"):
            rep["status"] = "REVIEW_REQUIRED"
    json.dump(rep, open(os.path.join(ldir, "localisation_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return rep


def run(episode_dir, bible, langs=None, **kw):
    cfg = json.load(open(os.path.join(ROOT, "studio", "pipeline", "languages.json"), encoding="utf-8"))
    src = cfg.get("source", "tr")
    todo = langs or [c for c, v in cfg["languages"].items() if v.get("enabled") and c != src]
    return [build_lang_dir(episode_dir, bible, c, cfg["languages"][c], **kw) for c in todo if c in cfg["languages"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode-dir", required=True); ap.add_argument("--series", required=True); ap.add_argument("--langs")
    a = ap.parse_args()
    bible = json.load(open(a.series, encoding="utf-8"))
    for r in run(a.episode_dir, bible, a.langs.split(",") if a.langs else None):
        print("%s: %s | %d satır | çevrilmeyen: %d | ses sorunu: %d" % (r["lang"], r["status"], r["lines"], len(r["untranslated"]), len(r["voice_problems"])))


if __name__ == "__main__":
    main()
