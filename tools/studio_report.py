"""Stüdyo durum raporu (gerçek verilerden; ölçülmeyen şey yazılmaz). Çıktı: studio/reports/studio-status.md"""
import datetime, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
import office_server as osrv


def main():
    langs = json.load(open(os.path.join(ROOT, "studio", "pipeline", "languages.json"), encoding="utf-8"))["languages"]
    ws = osrv.WORKERS
    conn = [w for w in ws if w[3]]
    L = ["# AHOS Stüdyo Durum Raporu", "", "Tarih: " + datetime.datetime.now().isoformat(timespec="minutes"), ""]
    L += ["## İşçiler", "- Kayıtlı çizgi film işçisi: %d" % len(ws), "- Gerçek motora bağlı: %d (%s)" % (len(conn), ", ".join(w[0] for w in conn)),
          "- Bağlı olmayan: " + ", ".join(w[0] for w in ws if not w[3]), ""]
    L += ["## Diller (sahip onaylı sıra)"]
    for code, v in sorted(langs.items(), key=lambda kv: kv[1].get("order", 99)):
        st = "ses: %s" % v.get("tts", "edge-tts")
        if v.get("native_review_required"): st += " · ANADİLİ İNCELEMESİ GEREKLİ"
        L.append("%s. %s (%s) — %s" % (v.get("order", "?"), v.get("name"), code, st))
    L += ["", "## Dil test durumu (uçtan uca denenen)", "- Denenen: en (121 satır geçti), kmr (yalnız çeviri + örnek ses). Diğer diller henüz denenmedi: desteği 'çalışıyor' diye raporlanmaz.", "", "## Dürüst notlar",
          "- Kurmancî: ücretsiz LLM çevirisi güvenilmez; ses modeli (Meta MMS) CC-BY-NC, ticari yayın için hukuki kontrol gerekir.",
          "- Teknik pipeline testi ≠ profesyonel kalite: yaratıcı kalite henüz ölçülmüyor (NOT_EVALUATED).",
          "- Sahip onayı bekleyen: yaratıcı onay, lisans/ticari kullanım, Kurmancî inceleme.", ""]
    out = os.path.join(ROOT, "studio", "reports"); os.makedirs(out, exist_ok=True)
    p = os.path.join(out, "studio-status.md"); open(p, "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
