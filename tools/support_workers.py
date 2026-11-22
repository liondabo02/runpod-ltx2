#!/usr/bin/env python3
"""AHOS destek işçileri: rights (hak/lisans), finance (maliyet), analytics (ölçüm), distribution (yayın paketi), research (referans notları).
Hepsi yerel ve ağsız çalışır; hiçbir şeyi yüklemez/yayınlamaz/harcamaz. Çıktı: episode_dir altına JSON."""
import argparse, glob, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
LANGS = os.path.join(ROOT, "studio", "pipeline", "languages.json")
BUDGET_EUR = 1.0
NC_MODELS = ("mms-tts",)  # CC-BY-NC: parayla yayında riskli


def _j(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return d


def _w(ep, name, obj):
    os.makedirs(ep, exist_ok=True); p = os.path.join(ep, name)
    json.dump(obj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1); return p


def rights(ep):
    """Kullanılan kaynakların lisans durumu. Bilinmeyen = REVIEW (sahte PASS yok)."""
    flags = []
    mm = _j(os.path.join(ep, "audio", "music_manifest.json"), {})
    music = "OK_PROCEDURAL" if mm else "UNKNOWN"
    if not mm:
        flags.append("müzik manifesti yok: telif durumu doğrulanamadı")
    cfg = _j(LANGS, {}) or {}
    for code, l in (cfg.get("languages", cfg) if isinstance(cfg.get("languages", cfg), dict) else {}).items():
        if isinstance(l, dict) and l.get("enabled") and any(n in str(l.get("mms_model", "")) for n in NC_MODELS):
            flags.append("%s: MMS-TTS CC-BY-NC (ticari/gelirli yayın için izin gerekir)" % code)
    for f in glob.glob(os.path.join(ep, "**", "*.mp3"), recursive=True)[:1]:
        flags.append("kaynağı bilinmeyen mp3: " + os.path.basename(f))
    st = "REVIEW_REQUIRED" if flags or music == "UNKNOWN" else "PASSED"
    return _w(ep, "rights_report.json", {"status": st, "music": music, "flags": flags,
              "note": "hukuki tavsiye değildir; yalnız teknik kayıt"})


def finance(ep):
    """Yerel işlerde 0 EUR; manifestlerdeki cost_eur toplanır, 1 EUR/bölüm sınırı denetlenir."""
    total, items = 0.0, {}
    for p in glob.glob(os.path.join(ep, "**", "*manifest*.json"), recursive=True):
        c = (_j(p, {}) or {}).get("cost_eur")
        if isinstance(c, (int, float)):
            items[os.path.relpath(p, ep)] = c; total += c
    st = "PASSED" if total <= BUDGET_EUR else "OVER_BUDGET"
    return _w(ep, "finance_report.json", {"status": st, "total_eur": round(total, 4), "budget_eur": BUDGET_EUR,
              "items": items, "note": "yalnız manifestte yazan maliyetler; ücretli API onaysız kullanılmaz"})


def analytics(ep):
    """Bölümün teknik ölçümleri (izleyici verisi değil; yayın sonrası analiz ayrı)."""
    sheet = _j(os.path.join(ep, "beat_sheet.json"), {}) or {}
    beats = sheet.get("beats", [])
    dur = float(beats[-1]["t_end"]) if beats else 0.0
    speakers = {}
    for b in beats:
        for k in ("speaker", "character"):
            if b.get(k):
                speakers[b[k]] = speakers.get(b[k], 0) + 1
    cuts = len(beats)
    rm = _j(os.path.join(ep, "render", "render_manifest.json"), {}) or {}
    out = {"duration_s": dur, "beats": cuts, "avg_beat_s": round(dur / cuts, 2) if cuts else None,
           "speakers": speakers, "frames": rm.get("frames"), "meets_480s": dur >= 480, "audience_data": "NOT_AVAILABLE"}
    return _w(ep, "analytics_report.json", out)


def distribution(ep, series_title="AHOS"):
    """Yayın paketi taslağı (başlık/açıklama/diller). YÜKLEME YAPMAZ."""
    cfg = _j(LANGS, {}) or {}
    langs = cfg.get("languages", cfg)
    codes = [c for c, l in langs.items() if isinstance(l, dict) and l.get("enabled")] if isinstance(langs, dict) else []
    rep = _j(os.path.join(ep, "rights_report.json"), {}) or {}
    ready = rep.get("status") == "PASSED"
    pkg = {"status": "DRAFT_NOT_UPLOADED", "title": series_title + " - " + os.path.basename(ep), "languages": codes,
           "ai_disclosure": True, "blocked_by_rights": not ready,
           "note": "yükleme/yayın yalnız sahibin onayıyla; yapay zekâ üretimi etiketi eklenir"}
    return _w(ep, "distribution_package.json", pkg)


def research(note, source=""):
    """Referans/öğrenilen fikir notunu studio/research/references.jsonl dosyasına ekler (web gezmez)."""
    d = os.path.join(ROOT, "studio", "research"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "references.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": source, "note": note}, ensure_ascii=False) + "\n")
    return "ok"


def run_all(ep):
    return {"rights": rights(ep), "finance": finance(ep), "analytics": analytics(ep), "distribution": distribution(ep)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--episode-dir", required=True)
    print(json.dumps(run_all(ap.parse_args().episode_dir), ensure_ascii=False, indent=1))
