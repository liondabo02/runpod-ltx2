# AHOS-QUALITY-99 — Başlangıç Ölçümü (Baseline)

Tarih: 2026-10-18 · Ölçülen commit: `32bc435` (izole worktree) · Ölçüm yöntemi: gerçek test koşusu + canlı runtime kayıtları (salt-okunur).

> Not: Ana çalışma ağacında başka bir ajanın **commit edilmemiş** çalışması var
> (`autoschedule.py`, `recovery.py`, `external_checks.py`, soak testleri).
> Bu dosyalar baseline'a **dahil edilmedi**; ölçüm yalnız commit edilmiş ağaç üzerinden yapıldı.

## Ölçülen temel göstergeler

| Gösterge | Değer |
|---|---|
| Test sonucu (izole worktree) | **508 passed**, 29.3 sn, exit 0 |
| Modül sayısı (`ahos_core/ahos`) | 91 |
| Satır sayısı | 21 698 |
| Test dosyası | 83 (`ahos_core`) + 14 (`control_plane_v2`) |
| Kuyruk | 60 completed, 6 blocked |
| Kanıt defteri | 6 görev kaydı; 5'inde gerçek dosya değişikliği; 4'ü filesystem kaynaklı |
| Model harcaması | 6 geçmiş çağrı, toplam **$0.0111** (17 Ekim); bugün 0 |
| Paneller | 8766 güncel kod (autonomy executed=2); 8765 eski kod (autonomy alanı yok) |
| Boş RAM | 1.5 GiB (14.5/15.7 kullanımda) — yerel model eşiği 2 GiB |
| Daemon | çalışıyor, `executor_mode=deterministic`, `no_evidence_streak=0` |

## 15 alanın başlangıç durumu

| # | Alan | Ölçüm / kanıt | Durum | Eksik |
|---|---|---|---|---|
| 1 | Mimari güvenilirlik | 508 test, 91 modül; tek süreçli panel + ayrı daemon | ⚠️ | İki panel farklı kod çalıştırıyor; panel/daemon durum birleşmiyor |
| 2 | Ajanların gerçek iş yapması | 6 görevin 5'i dosya değiştirdi; hepsi deterministik işçi | ⚠️ | Görev metnine göre özellik üretimi yok (LLM yolu RAM'e takılı) |
| 3 | Kalıcı görev kuyruğu | SQLite, 66 kayıt; lease/attempt alanları; **100 sentetik görev: 1.97 sn, 100/100 tamam, kayıp/tekrar yok**, tekrar oynatma idempotent | ✅ | — (bloklu kayıtların 3'ü eski kod hatası) |
| 4 | Çökme sonrası kurtarma | `recovery.py` **commit edilmemiş** (başka ajan); committed ağaçta yok | ❌ | Kurtarma yolu baseline'da yok; canlıda yalnız panel başlangıcında |
| 5 | Eşzamanlı görev güvenliği | `test_project_lock_xproc`, `test_lock_observability`; OS kilidi + fail-closed `unknown-owner` | ✅ | — |
| 6 | Dosya/veri bütünlüğü | SHA-256 kanıt, kabul kapısı hash pinleme, yeni filesystem delivery defteri | ✅ | — |
| 7 | Codex–DeepSeek görev paylaşımı | `taskboard.py`: kalıcı görev kimliği, tek sahip, lease + heartbeat, **kanıtsız kapanmayan** görev, CLI; 11 test (4 eşzamanlı claim → 1 kazanan) | ⚠️ | Pano hazır; diğer ajanın kullanması ve konsol entegrasyonu henüz yok |
| 8 | Otomatik test kapsamı | `pytest-cov` ile ölçüldü: **ahos toplam %83** (10 525 satır). Kritik: autonomy %88, owner_console %88, delivery %88, project_qa %87, daemon %83, local_ollama %73. 0%: `owner_cli`, `source_context` | ⚠️ | Kapsam artık ölçülüyor; 0% modüller ve %70 altı kalanlar kapatılmalı |
| 9 | Güvenlik / yetkilendirme | Onay girişi, kill-switch, panel token; `local_ollama` güvenlik kapıları artık testli (9 test: sabit localhost/model, 2 GiB, kilit, indirme yok) | ✅ | — |
| 10 | API / token maliyeti | Geçmişte 6 ücretli çağrı ($0.0111); `paid_calls` artık defterden okunuyor | ⚠️ | Otomatik $0 politikası yalnız autonomy'de; executor seviyesinde tavan yok |
| 11 | Kalıcı hafıza | Dedupe günlüğü, audit zinciri, live-events, worker metrics | ✅ | — |
| 12 | Başkanlık paneli | 8766 güncel; 8765 eski; daemon heartbeat panelde yok | ⚠️ | Panel tek kaynak değil; daemon durumu görünmüyor |
| 13 | Gerçek ürün üretimi | Mipiluna'da deterministik iyileştirme kataloğu tükendi (0 dosya → 1 dosya arası); Foundry'de veri dosyaları değişiyor | ❌ | Katalog sonrası gerçek özellik üretimi yok |
| 14 | Android / tarayıcı doğrulaması | Headless tarayıcı: Mipiluna **yüklendi** (219 862 bayt DOM, 6.4 sn, 0 problem, ekran görüntüsü `quality/evidence/browser/browser.png`) | ⚠️ | Android APK/emülatör kanıtı yok; etkileşim senaryosu (kart tıklama) yok |
| 15 | İzleme, hata kaydı, yeniden deneme | Metrikler, canlı olaylar, sınırlı retry, daemon heartbeat; **merkezî `errors.jsonl` + `ahos-errors` CLI** eklendi (traceback, görev kimliği, boyut döndürme) | ⚠️ | Panel bu günlüğü henüz göstermiyor; diğer süreçler kendi hatalarını yazmıyor |

**Durum dağılımı:** 5 ✅ · 7 ⚠️ · 3 ❌ — hiçbir alan "tamamlandı" ilan edilmedi.

## Öncelikli eksikler (etki sırası)

1. **Gerçek özellik üretimi (13/2)** — deterministik katalog tükendi; yerel model yolu RAM eşiğine takılı. Bu, "holding kendi kendini geliştiriyor" iddiasının en zayıf halkası.
2. **Çökme kurtarma (4)** — kurtarma kodu commit edilmiş ağaçta yok; yeniden başlatma sonrası yarım görev davranışı kanıtsız.
3. **Panel tekilliği (12)** — 8765/8766 farklı kod; daemon heartbeat görünmüyor.
4. **Codex–DeepSeek sözleşmesi (7)** — iki ajan arasında yazılı görev devri yok.
5. **Kapsam ölçümü (8)** — 508 test var ama hangi kodun test edildiği bilinmiyor.

## Başarı kriterleri (%99 için)

- Kritik testlerin tamamı yeşil; yüksek önemde açık hata yok.
- Her alan için **ölçülmüş** kanıt (komut + çıktı) `quality/evidence/` altında.
- Ürün çıktısı: en az bir gerçek, istenen özellik — dosya farkı + test + tarayıcı kanıtı.
- Panel tek kaynak: 8765/8766 aynı kodu ve aynı durumu gösterir.
- Ücretli çağrı: 0 (defterden doğrulanmış).
- Kurtarma: yarım görev yeniden başlatmada çift çalışmaz, kaybolmaz.
