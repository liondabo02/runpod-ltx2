#!/usr/bin/env python3
"""AHOS beat_sheet doğrulayıcı (yalnız standart kütüphane).

Kullanım: python tools/validate_beat_sheet.py beat_sheet.json [series-bible.json] [--target 480]
Çıkış kodu 0 = kurallar geçti, 1 = en az bir hata. Yaratıcı kaliteyi ÖLÇMEZ.
"""
import json, re, sys

MIN_BEAT, MAX_BEAT = 4.0, 12.0
MIN_WORDS_PER_MIN = 15          # çok sessiz = çocuk dizisi için zayıf
MAX_WORDS_PER_MIN = 60          # diyalog üst sınırı (çocuk içeriği: az konuşma)
RISKY = [  # (bebek/küçük çocuk + riskli nesne) güvenlik taraması
    r"\bip(i|e|in|le|ten|ler\w*)?\b", r"\bkordon", r"\bşerit", r"\bküçük parça", r"\bboğ", r"\bdola[nş]",
    r"\brope\b", r"\bstring\b", r"\bstrap", r"\bchoke",
]
REQUIRED = ["t_start", "t_end", "scene_id", "location", "characters", "action", "emotion", "camera", "sound"]


def validate(sheet, bible=None, target=480):
    errors, warnings = [], []
    beats = sheet.get("beats") if isinstance(sheet, dict) else None
    if not beats:
        return ["beats listesi boş veya yok"], warnings
    chars = {c["id"] for c in (bible or {}).get("characters", [])} if bible else None
    locs = {l["id"] for l in (bible or {}).get("locations", [])} if bible else None
    prev_end, words, last_action, prev_toks = 0.0, 0, None, None
    for i, b in enumerate(beats):
        tag = f"beat[{i}]"
        for k in REQUIRED:
            if k not in b or b[k] in (None, "") or (b[k] == [] and k != "characters"):   # boş karakter listesi = manzara planı, geçerli
                errors.append(f"{tag}: '{k}' eksik")
        try:
            s, e = float(b["t_start"]), float(b["t_end"])
        except Exception:
            errors.append(f"{tag}: t_start/t_end sayı değil"); continue
        if abs(s - prev_end) > 0.5:
            errors.append(f"{tag}: zaman boşluğu/çakışma (beklenen {prev_end}, gelen {s})")
        d = e - s
        if d < MIN_BEAT or d > MAX_BEAT:
            errors.append(f"{tag}: süre {d:.1f}s, izinli {MIN_BEAT}-{MAX_BEAT}s")
        prev_end = e
        act = str(b.get("action", ""))
        if last_action and act.strip().lower() == last_action:
            errors.append(f"{tag}: önceki vuruşla aynı eylem (sahte uzatma)")
        toks = set(re.findall(r"\w+", act.lower()))
        if prev_toks and toks and len(toks & prev_toks) / max(1, len(toks | prev_toks)) > 0.7:
            errors.append(f"{tag}: önceki vuruşa çok benziyor (tekrar)")
        prev_toks = toks
        last_action = act.strip().lower()
        dlg = str(b.get("dialogue", "") or "")
        words += len(dlg.split())
        txt = (act + " " + dlg).lower()
        for pat in RISKY:
            if re.search(pat, txt) and any(x in txt for x in ("bebek", "kaan", "baby", "infant")):
                warnings.append(f"{tag}: güvenlik incelemesi gerekir ({pat}) -> safety_note ve yetişkin kontrolü şart")
                if not b.get("safety_note"):
                    errors.append(f"{tag}: riskli içerik var ama safety_note boş")
        if chars is not None:
            for c in b.get("characters", []):
                if c not in chars:
                    errors.append(f"{tag}: bible'da olmayan karakter '{c}'")
        if locs is not None and b.get("location") and b["location"] not in locs:
            errors.append(f"{tag}: bible'da olmayan mekân '{b['location']}'")
    if prev_end < target - 2:
        errors.append(f"toplam süre {prev_end:.0f}s < hedef {target}s")
    wpm = words / (prev_end / 60) if prev_end else 0
    if prev_end and wpm < MIN_WORDS_PER_MIN:
        errors.append(f"diyalog çok az: {wpm:.0f} kelime/dk (en az {MIN_WORDS_PER_MIN})")
    if wpm > MAX_WORDS_PER_MIN:
        warnings.append(f"diyalog yoğunluğu yüksek: {wpm:.0f} kelime/dk")
    first = beats[0]
    if float(first.get("t_end", 99)) > 15 and not str(first.get("action", "")).strip():
        errors.append("ilk 15 sn içinde görsel kanca yok")
    return errors, warnings


def main(argv):
    target = 480
    if "--target" in argv:
        i = argv.index("--target"); target = float(argv[i + 1]); del argv[i:i + 2]
    if len(argv) < 2:
        print(__doc__); return 2
    sheet = json.load(open(argv[1], encoding="utf-8"))
    bible = json.load(open(argv[2], encoding="utf-8")) if len(argv) > 2 else None
    errors, warnings = validate(sheet, bible, target)
    for w in warnings: print("UYARI:", w)
    for e in errors: print("HATA:", e)
    print("SONUÇ:", "GEÇTİ" if not errors else f"KALDI ({len(errors)} hata)")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
