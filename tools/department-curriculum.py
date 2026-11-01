"""Departman müfredatı: her departmanın hatalarından ders çıkar ve öğret.

1) Kuyruktaki engelli görevlerin nedenlerini departman bazında toplar.
2) İşçi karnelerinden zayıf halkaları çıkarır.
3) Her departman için kısa bir müfredat belgesi (markdown) yazar.
4) Belgeyi bilgi ağına (skill cards) aktarır; böylece sonraki görevlerde
   prompt'a otomatik enjekte edilir.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")

# Departman bazlı temel kurallar + hata desenlerine karşılık gelen dersler
BASE_RULES = {
    "oyun": [
        "Yama uygulamadan önce hedef dosyanın gerçekten var olduğunu doğrula (yol + uzantı).",
        "Dosya değişmediyse teslim yoktur: '0 dosya değişti' asla tamamlandı sayılmaz.",
        "Her oyun değişikliğinden sonra `node --check` ve proje kabul kapısını çalıştır.",
        "Ses dosyaları: `www/voices/` altında; HTML'de `voices/...` yoluyla çağır.",
    ],
    "software": [
        "Küçük, tek amaçlı yamalar üret; her yamayı kabul kapısıyla doğrula.",
        "Kod değişikliğinde önce testi yaz, sonra uygula; test geçmeden teslim sayma.",
        "Hata günlüğündeki son nedeni tekrar üret, sonra düzelt.",
    ],
    "creative": [
        "Her üretimde gerçek medya dosyası (mp4/wav/png >1KB) üret; plan belgesi tek başına teslim değildir.",
        "Jenerik için sahne listesi, ses kaynağı ve süre yaz.",
        "Karakter sesleri: öğretmen (sıcak, yavaş) ve çocuk (tatlı) ayrı tutulur.",
    ],
    "data": [
        "Rapor istendiğinde gerçek kaynaktan sayı al (SQLite/ledger); tahmin yazma.",
        "Çıktıyı JSON istenmişse geçerli JSON üret; markdown istenmişse tablo kullan.",
        "Rapor sonunda '## Özet' ve tarih damgası olsun.",
    ],
    "finance": [
        "Her harcama satırında model adı, çağrı sayısı ve USD alanı olsun.",
        "Ücretsiz kaynak (yerel/tünel) ile ücretli kaynağı ayrı göster.",
        "Bütçe önerisi verirken varsayımı açıkça yaz.",
    ],
    "guvenlik": [
        "Son 24 saatte ücretli model çağrısı var mı kontrol et; varsa raporla.",
        "Proje kilitlerinin sahibini ve pid'ini doğrula; sahipsiz kilidi raporla.",
        "Şüpheli davranışta eylem önerisi yaz (3 madde).",
    ],
    "quality": [
        "Kabul kapısı sonuçlarını dosya bazında listele; geçmeyen kontrolü adıyla yaz.",
        "Boş teslim (0 dosya) ve kabul hatasını ayırt et.",
        "Kontrol önerisi yazarken 'neden gerekli' maddesi ekle.",
    ],
    "research": [
        "Önerileri kanıta dayandır; kaynak veya gerekçe yaz.",
        "Okul öncesi için kısa cümle, somut nesne, renk ve ses kullanımı öner.",
        "Her öneri için uygulama adımı ekle.",
    ],
    "marketing": [
        "Veliye yönelik metinde güvenlik ve eğitsel fayda vurgula.",
        "3 cümleyi geçme; somut fayda + çağrı cümlesi kullan.",
        "Etik olmayan iddia (ücretsiz değilse ücretsiz deme) yazma.",
    ],
    "sales": [
        "Paket önerisinde içerik, fiyat, hedef kitle alanlarını doldur.",
        "Okul öncesi kurumlara uygun dil kullan; yasal/ticari iddia uydurma.",
        "Her paket için tek cümlelik değer önerisi yaz.",
    ],
    "support": [
        "Yanıtlar çocuk ve veli diliyle ayrı ayrı yazılmalı.",
        "Her yanıt 3 cümleyi geçmesin; çözüm adımı içersin.",
        "Bilinmeyen konuda 'emin değilim, ileteceğim' de.",
    ],
    "operations": [
        "Kontrol listesi maddeleri ölçülebilir olsun (sayı, süre, eşik).",
        "Her maddeye sorumlu ve sıklık yaz.",
        "Gecikme önlemlerinde tetikleyici ve eylem ayrı yazılır.",
    ],
    "infrastructure": [
        "Eşik değerleri sayıyla ver (disk %, RAM MiB, CPU %).",
        "Yedek planında sıklık, saklama süresi ve geri yükleme testi olsun.",
        "Uyarı kanalını (panel/log) belirt.",
    ],
    "holding": [
        "Haftalık özette departman, teslim, engel ve öneri alanları olsun.",
        "Hedefler ölçülebilir ve tek haftalık olsun.",
        "Çelişen hedef verme; öncelik sırası yaz.",
    ],
    "ai-platform": [
        "Sağlayıcı sağlığını ölç: base_url, model, süre, hata.",
        "Ücretsiz kaynakları önce dene; ücretliye geçişi gerekçelendir.",
        "Zaman aşımı ve token sınırını açıkça yaz.",
    ],
}


def analyse() -> tuple[dict, dict]:
    con = sqlite3.connect(R / "company-service.db")
    con.row_factory = sqlite3.Row
    reasons = defaultdict(Counter)
    for row in con.execute("select mission_id, last_error from missions where status='blocked'"):
        dept = (row["mission_id"].split("-")[1] if "-" in row["mission_id"] else "?")
        text = (row["last_error"] or "").lower()
        if "kilit" in text:
            key = "kilit"
        elif "timeout" in text or "zaman aşımı" in text:
            key = "zaman aşımı"
        elif "qa failed" in text or "unverified" in text:
            key = "QA"
        elif "executor_unavailable" in text or "yürütücü" in text:
            key = "yürütücü"
        elif "dosya yok" in text or "hedef" in text:
            key = "hedef dosya"
        else:
            key = "diğer"
        reasons[dept][key] += 1

    metrics = defaultdict(lambda: {"runs": 0, "ok": 0})
    ledger = R / "worker-metrics.jsonl"
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-4000:]:
            try:
                row = json.loads(line)
            except Exception:
                continue
            dept = str(row.get("department") or "?")
            metrics[dept]["runs"] += 1
            metrics[dept]["ok"] += 1 if row.get("success") else 0
    return reasons, metrics


def write_curriculum(reasons, metrics) -> list[Path]:
    inbox = R / "knowledge" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    written = []
    for department, rules in sorted(BASE_RULES.items()):
        failures = reasons.get(department, Counter())
        stat = metrics.get(department, {"runs": 0, "ok": 0})
        rate = (stat["ok"] / stat["runs"] * 100) if stat["runs"] else 0.0
        lines = [
            f"# {department} departmanı müfredatı",
            "",
            f"Oluşturuldu: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
            f"Ölçülen başarı: %{rate:.1f} ({stat['ok']}/{stat['runs']})",
            "",
            "## Zorunlu kurallar",
        ]
        for rule in rules:
            lines.append(f"- {rule}")
        if failures:
            lines += ["", "## Bu departmanda gözlenen hata sınıfları"]
            for key, count in failures.most_common():
                lines.append(f"- {key}: {count} görev")
        lines += [
            "",
            "## Teslim kuralı",
            "- Gerçek çıktı dosyası yoksa görev tamamlanmış sayılmaz.",
            "- Kabul kapısı geçmeden 'doğrulandı' yazılmaz.",
            "",
        ]
        path = inbox / f"mufredat-{department}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    reasons, metrics = analyse()
    paths = write_curriculum(reasons, metrics)
    print("yazılan müfredat:", len(paths))

    from ahos import skills

    total_cards = 0
    for path in paths:
        try:
            result = skills.learn(R, path, use_model=False)
            total_cards += int(result.get("cards") or 0)
        except Exception as exc:  # noqa: BLE001
            print("  öğrenilemedi:", path.name, exc)
    print("yeni beceri kartı:", total_cards)
    print("kart toplamı:", skills.stats(R))


if __name__ == "__main__":
    main()
