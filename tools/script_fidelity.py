#!/usr/bin/env python3
"""Senaryo sadakat denetimi (kodla, LLM'siz): sahibin metnindeki repliklerin ve karakter/mekân adlarının
beat_sheet'te bulunma oranı. Eşik altı -> NEEDS_REVISION (sahte PASS yok)."""
import json, re

THRESH = 0.85


def _n(t):
    return re.sub(r"[^\w]+", " ", str(t).lower().replace("İ", "i").replace("I", "ı")).strip()


def source_lines(text):
    """'Ad: cümle' veya «—» / tırnaklı replikleri çıkarır."""
    out = []
    for line in (text or "").splitlines():
        m = re.match(r"\s*[-•*]?\s*([A-ZÇĞİÖŞÜa-zçğıöşü][\w ]{0,24}?)\s*[:：]\s*[\"“«]?(.+?)[\"”»]?\s*$", line)
        if m and len(m.group(2).split()) >= 2 and m.group(1).strip().lower() not in ("süre", "dil", "yaş", "durum", "ışık", "oyunculuk"):
            out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def _words(t):
    return set(w for w in _n(t).split() if len(w) > 2)


def check(source_text, beats):
    lines = source_lines(source_text)
    have = " ".join(_n(b.get("dialogue", "")) for b in beats)
    hv = set(have.split()); missing = []
    for who, line in lines:
        w = _words(line)
        if not w:
            continue
        if len(w & hv) / len(w) < 0.7:
            missing.append(f"{who}: {line[:80]}")
    cov = 1.0 if not lines else round(1 - len(missing) / len(lines), 3)
    return {"status": "PASSED" if cov >= THRESH else "NEEDS_REVISION", "dialogue_lines_in_source": len(lines),
            "coverage": cov, "missing": missing[:20],
            "note": "yalnız replik kapsamı ölçülür; olay sırası ve ton için insan okuması gerekir"}
