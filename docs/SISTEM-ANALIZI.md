# AHOS sistem analizi

Üretim: 2026-11-01T19:01:59.420515+00:00

## Ölçüm

- Çekirdek modül: **182** (43657 satır)
- Test dosyası: **189**, test fonksiyonu: **1091**
- Departman: **16**, projesi bağlı: **16**, teslim edebilir (proje + kapı + pin): **15**
- Hazır departmanlar: creative, data, finance, genel, guvenlik, holding, infrastructure, marketing, operations, oyun, quality, research, sales, software, support

## Çalışan hatlar (kanıtlı)

| Hat | Kanıt |
|---|---|
| Kuyruk + lease + kurtarma | `queue`, `e2e: isci cokerse` |
| Tamamlanma bütünlüğü (stage-2) | DB tetikleyicileri + `test_completion_db_guard` |
| Kabul kapısı (QA) | `test_acceptance_trust`, `test_source_guards` |
| Uçtan uca yazılım teslimi | `E2E-VERIFIED-4` (delivery.verified=true) |
| 2D çizgi film üretimi | `studio_2d` + `studio_qa` (12 s ve 35 s pilot, skor 90) |
| Seslendirme + miksaj | `studio_voice` + `apad -t` (18 s sesli pilot, skor 100) |
| Klon paritesi | `clone_acceptance` (replica-skill araçları) |
| Ücretsiz API kataloğu | `api_catalog` (public-apis) |

## Açık uçlar

1. Türkçe ses: makinede yalnız de-DE/en-US SAPI sesleri var; piper `tr_TR` modeli yok.
2. Dudak senkronu: ağız replik süresine bağlı; ses zarfına bağlanmalı.
3. RunPod anahtarı yok: LTX-2 sinematik katman ve Kokoro ses devre dışı.
4. Kod modeli 7b: karmaşık yazılım görevlerinde yetersiz (kapı yakalıyor).
5. 8-10 dk bölüm üretim koşusu henüz yapılmadı (altyapı hazır, ~11 dk render).
