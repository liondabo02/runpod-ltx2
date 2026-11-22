"""Kendini geliştirme döngüsü: bölüm sonuçlarını ölçer, tekrarlayan hataları ders yapar, rapor yazar.
Güvenlik: kod DEĞİŞTİRMEZ, yaratıcı onay VERMEZ; yalnız metin dersi ekler (sınırlı, silinebilir)."""
import argparse, collections, datetime, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import lessons
ROOT = os.path.dirname(HERE)
REPORTS = os.path.join(ROOT, "studio", "reports")

# hata deseni -> (işçi, ders)
RULES = [
    (r"süre .*izinli|izinli 4-12", "writer", "Her vuruş 4-8 saniye olsun; 12 saniyeyi asla aşma."),
    (r"önceki vuruşla aynı eylem", "writer", "Art arda iki vuruşta aynı eylemi yazma; her vuruşta yeni bir eylem/duygu olsun."),
    (r"diyalog çok az", "writer", "Her vuruşta en az bir konuşma satırı yaz, 'İsim: replik' biçiminde ve karakter adıyla."),
    (r"zaman boşluğu|çakışma", "writer", "Vuruş sürelerini kesintisiz ardışık yaz: bir vuruş bittiği anda sonraki başlasın."),
    (r"görsel kanca", "writer", "İlk 15 saniyede dikkat çeken görsel bir olay (kanca) koy."),
    (r"bible'da olmayan", "writer", "Yalnız seri bible'ında tanımlı karakter ve mekânları kullan; yeni isim uydurma."),
    (r"safety_note boş", "writer", "Riskli bir sahne varsa safety_note alanını mutlaka doldur."),
    (r"toplam süre", "writer", "Toplam süre hedefe ulaşana kadar vuruş ekle; erken bitirme."),
    (r"sığmadı|vuruş süresine", "writer", "Diyaloğu vuruş süresine sığacak kadar kısa yaz (saniyede ~2.5 kelime)."),
]

def _read_json(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None

def collect(out_dir):
    rows = []
    for ep in sorted(glob.glob(os.path.join(out_dir, "*"))):
        if not os.path.isdir(ep):
            continue
        texts, m = [], {"episode": os.path.basename(ep)}
        for f in glob.glob(os.path.join(ep, "**", "*.json"), recursive=True):
            if "lang" in f.split(os.sep):
                continue
            d = _read_json(f)
            if d is None:
                continue
            texts.append(json.dumps(d, ensure_ascii=False))
            if f.endswith("render_manifest.json"):
                m["sec_per_frame"] = d.get("sec_per_frame")
            if f.endswith("video_qa.json") or f.endswith("qa_report.json"):
                m["qa"] = d.get("status") or d.get("verdict")
        m["text"] = "\n".join(texts)
        rows.append(m)
    return rows

def analyse(rows):
    cnt = collections.Counter()
    for m in rows:
        for pat, w, ls in RULES:
            if re.search(pat, m["text"], re.I):
                cnt[(w, ls)] += 1
    return cnt

def run(out_dir=None, min_hits=2, dry=False):
    out_dir = out_dir or os.path.join(ROOT, "out")
    rows = collect(out_dir)
    cnt = analyse(rows)
    added = []
    for (w, ls), n in cnt.items():
        if n >= min_hits and not dry:
            lessons.add(w, ls, source="auto", count=n); added.append((w, ls, n))
    os.makedirs(REPORTS, exist_ok=True)
    now = datetime.datetime.now()
    with open(os.path.join(REPORTS, "metrics.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now.isoformat(timespec="seconds"), "episodes": len(rows),
                            "patterns": {f"{w}:{ls}": n for (w, ls), n in cnt.items()}}, ensure_ascii=False) + "\n")
    rep = os.path.join(REPORTS, f"improvement-{now:%Y-%m-%d}.md")
    with open(rep, "w", encoding="utf-8") as f:
        f.write(f"# Gelişim raporu {now:%Y-%m-%d %H:%M}\n\nİncelenen bölüm: {len(rows)}\n\n## Tekrarlayan sorunlar\n")
        for (w, ls), n in cnt.most_common():
            f.write(f"- ({n} bölüm) [{w}] {ls}\n")
        f.write("\n## Bu turda eklenen dersler\n" + ("\n".join(f"- [{w}] {ls} ({n}x)" for w, ls, n in added) or "- yok") + "\n")
        f.write("\n## Sahip için notlar\n- Dersleri görmek: python tools\\give_feedback.py --list writer\n- Yanlış dersi silmek: --retire \"metin\"\n")
    return {"episodes": len(rows), "added": added, "report": rep}

if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--out-dir"); p.add_argument("--min-hits", type=int, default=2); p.add_argument("--dry", action="store_true")
    a = p.parse_args(); r = run(a.out_dir, a.min_hits, a.dry)
    print("Bölüm:", r["episodes"], "| Yeni ders:", len(r["added"]), "| Rapor:", r["report"])
