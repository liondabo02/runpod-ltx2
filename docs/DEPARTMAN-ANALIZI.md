# Departman analizi ve ücretsiz üretim planı

Her departman için: ajan/yetkinlik sayısı, bağlı proje, kabul kapısı,
bugün ürettiği teslim türü ve kullandığı ücretsiz araç seti.

| Departman | Ajan | Yetkinlik | Proje | Kapı | Teslim türü |
|---|---|---|---|---|---|
| Yapay Zekâ Platformu (`ai-platform`) | 0 | 0 | harun-ai-foundry | var (pinsiz) | kod |
| Çizgi Film Stüdyosu (`creative`) | 0 | 0 | creative-workspace | var (pinned) | çizgi film bölümü |
| Veri Departmanı (`data`) | 0 | 0 | data-workspace | var (pinned) | belge |
| Finans Departmanı (`finance`) | 0 | 0 | finance-workspace | var (pinned) | belge |
| Genel İş Departmanı (`genel`) | 0 | 0 | genel-workspace | var (pinned) | belge |
| Güvenlik ve Kaynak Koruma Departmanı (`guvenlik`) | 0 | 0 | guvenlik-workspace | var (pinned) | belge |
| Holding Yönetimi (CEO) (`holding`) | 0 | 0 | holding-workspace | var (pinned) | belge |
| Altyapı Departmanı (`infrastructure`) | 0 | 0 | infrastructure-workspace | var (pinned) | belge |
| Pazarlama Departmanı (`marketing`) | 0 | 0 | marketing-workspace | var (pinned) | belge |
| Operasyon Departmanı (`operations`) | 0 | 0 | operations-workspace | var (pinned) | belge |
| Oyun Geliştirme Departmanı (`oyun`) | 0 | 0 | mipiluna | var (pinned) | kod |
| Kalite Departmanı (`quality`) | 0 | 0 | quality-workspace | var (pinned) | belge |
| Araştırma Departmanı (`research`) | 0 | 0 | research-workspace | var (pinned) | belge |
| Satış Departmanı (`sales`) | 0 | 0 | sales-workspace | var (pinned) | belge |
| Yazılım Şirketi (`software`) | 0 | 0 | pilot-software | var (pinned) | kod |
| Müşteri Destek Departmanı (`support`) | 0 | 0 | support-workspace | var (pinned) | belge |

## Üretim koşusu kanıtı (bu oturum)

| Görev | Durum | Kanıt |
|---|---|---|
| `FIN-TEST-2` (bütçe planı) | completed | `delivery.verified=true`, qa_worker_ids dolu |
| `MKT-TEST-2` (kanal planı) | completed | `delivery.verified=true`, qa_worker_ids dolu |
| 8 dk Türkçe bölüm | geçti (skor 100) | `C:\ahos-pilot\full-episode\acceptance.json` |

## Nasıl çalışıyor

1. Görev kuyruğa girer, yönetici brief üretir.
2. Üretim adımı departmanın projesine **gerçek teslim** yazar (`deliverables/`).
3. Projenin kabul kapısı (`tools/check_offline.py`) dosyayı denetler.
4. Bağımsız QA kanıtı inceler; `delivery.verified` ancak o zaman true olur.
5. `completed` yalnızca bu zincir geçerse yazılır (DB tetikleyicisi de zorlar).

Maliyet: 0 $ — model çağrısı yok, ücretli araç yok.

## Yapay Zekâ Platformu (`ai-platform`)

- **Araçlar**: yerel model (ollama), edge-tts, provider zinciri
- **Çıktılar**: model karşılaştırması, maliyet notu, seçim gerekçesi
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Çizgi Film Stüdyosu (`creative`)

- **Araçlar**: studio_2d (kod ile çizim), edge-tts (Türkçe nöral ses), ffmpeg montaj, studio_qa kabul kapısı
- **Çıktılar**: bölüm senaryosu, sahne planı, seslendirme, kapı raporu
- **Durum**: üretim koşusu yapıldı

## Veri Departmanı (`data`)

- **Araçlar**: DuckDB / pandas, açık veri setleri (data.gov, Kaggle), pandera ile şema doğrulama
- **Çıktılar**: veri sözlüğü, kalite raporu, özet istatistikler
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Finans Departmanı (`finance`)

- **Araçlar**: Python + pandas ile bütçe tablosu, GnuCash (ücretsiz muhasebe), Excel/Sheets şablonu, vergi takvimi hatırlatıcıları
- **Çıktılar**: aylık nakit akışı, gelir-gider özeti, risk listesi
- **Durum**: üretim koşusu yapıldı

## Genel İş Departmanı (`genel`)

- **Araçlar**: Markdown plan, kontrol listesi
- **Çıktılar**: hedef, adımlar, kabul kriteri
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Güvenlik ve Kaynak Koruma Departmanı (`guvenlik`)

- **Araçlar**: sır taraması (git grep + entropy), yedek doğrulama, erişim denetimi (kim neyi görebiliyor)
- **Çıktılar**: risk kaydı, sır envanteri, erişim matrisi
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Holding Yönetimi (CEO) (`holding`)

- **Araçlar**: portföy özeti (kuyruk verisinden), karar kaydı (ADR)
- **Çıktılar**: departman durumu, karar günlüğü, öncelik listesi
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Altyapı Departmanı (`infrastructure`)

- **Araçlar**: Windows Task Scheduler, robocopy yedekleme, uptime izleme
- **Çıktılar**: yedekleme planı, izleme listesi, geri dönüş adımları
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Pazarlama Departmanı (`marketing`)

- **Araçlar**: Google Search Console (ücretsiz), Google Analytics 4 (ücretsiz), Mailchimp ücretsiz plan, içerik takvimi (Markdown)
- **Çıktılar**: kanal planı, içerik takvimi, mesaj matrisi
- **Durum**: üretim koşusu yapıldı

## Operasyon Departmanı (`operations`)

- **Araçlar**: Task Scheduler / cron, süreç diyagramı (Mermaid), RACI tablosu
- **Çıktılar**: süreç adımları, sorumluluk matrisi, otomasyon fırsatları
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Oyun Geliştirme Departmanı (`oyun`)

- **Araçlar**: Godot 4 (ücretsiz), Phaser (web), Aseprite alternatifi: LibreSprite
- **Çıktılar**: oyun döngüsü, varlık listesi, test senaryoları
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Kalite Departmanı (`quality`)

- **Araçlar**: pytest + kabul kapıları, kontrol listesi (Markdown)
- **Çıktılar**: kabul kriterleri, test kapsamı, bulgu listesi
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Araştırma Departmanı (`research`)

- **Araçlar**: arXiv / OpenAlex / Semantic Scholar (ücretsiz API), Crossref DOI doğrulama, Zotero (ücretsiz)
- **Çıktılar**: araştırma sorusu, kaynak listesi (DOI'li), bulgular + sınırlar
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Satış Departmanı (`sales`)

- **Araçlar**: SQLite tabanlı CRM-lite, teklif şablonu, e-posta takip scripti
- **Çıktılar**: satış hunisi, teklif taslağı, haftalık takip listesi
- **Durum**: altyapı hazır, ilk koşu bekliyor

## Yazılım Şirketi (`software`)

- **Araçlar**: pytest, kabul kapısı (tools/check_offline.py), git worktree
- **Çıktılar**: değişiklik özeti, test sonucu, geri alma planı
- **Durum**: üretim koşusu yapıldı

## Müşteri Destek Departmanı (`support`)

- **Araçlar**: SQLite ticket kuyruğu, SSS bankası, yanıt şablonları
- **Çıktılar**: SSS, yanıt süresi hedefi, eskalasyon kuralı
- **Durum**: altyapı hazır, ilk koşu bekliyor
