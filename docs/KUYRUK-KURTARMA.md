# AHOS V5 — Kuyruk Kurtarma Raporu (pano kaynaklı engeller)

Tarih: 2026-11-07 · Dal: `feature/agent-control-plane` · Ölçüm: canlı DB
`ahos_core/runtime/company-service.db`

## Neden bu engeller "iş" değil "kuyruk durumu" hatasıydı?

37 görev `görev panosu biçimi geçersiz; mevcut veriler korunuyor` hatasıyla
engellenmişti. Kök neden görevin kendisi değil, o sırada okunamayan
`runtime/taskboard.json` dosyasıydı (yazıcı artık `tmp + os.replace` kullanıyor).
Pano bugün **geçerli**; bu yüzden tekrar deneme, panonun hâlâ geçerli olması
**ön koşuluyla** güvenli.

## Politika (neden toplu tekrar değil?)

1. Orijinal satır **silinmez**, engelli kalır (kanıt korunur).
2. Tekrar `-rN` kimliğiyle **yeni** görev olarak açılır.
3. Pano geçerli değilse araç **fail-closed** durur (`ValueError`), hiç kayıt açmaz.
4. Bir kez doğrulanmış çocuk (`completed`) varsa aynı kök görev **tekrar açılmaz** (idempotent).
5. Kapsam `--match` ve `limit` ile sınırlanır; "hepsini dene" yok.

## Sonuç (pano kaynaklı 12 engel)

| Ölçüm | Değer |
|---|---|
| Tekrar açılan görev | **13** (12 departman + ilk denemede ai-platform için r3) |
| Tamamlanan | **13 / 13** |
| `delivery.verified=1` | **13 / 13** |
| Üretilen gerçek belge | **39** (her görev: brief + doküman + QA review) |
| Orijinaller | 37'nin tamamı **blocked** kaldı |

Departmanlar: ai-platform, creative, data, finance, genel, guvenlik, holding,
infrastructure, marketing, operations, oyun, quality.
Örnek çıktı: `runtime/artifacts/documents/ai-platform-mission-objective--tasarım-dokümanı-üret-1794045130.md`
(1.683 bayt), `quality-review-1794045131245.md` (533 bayt).

**İdempotentlik kanıtı:** ikinci çalıştırmada aynı 12 kök için
`"candidates": 0, "skipped_recovered": 12` döndü; hiç yeni görev açılmadı.

## Kalan 25 neden tekrar edilmedi?

| Sınıf | Adet | Karar |
|---|---|---|
| `*-crisis-*` (aynı kök nedenin 20 kopyası) | 20 | Triyaj kuralı: kök neden tek görevle izlenir; kopyalar tekrar edilmez |
| `CMD-sales-arge-*` | 2 | Bağlam değişmiş; elle inceleme |
| `CMD-software-ahos-ideas-py-*` | 3 | Hedef dosya yeni proje kökünde yok (`pilot-software/ahos/ideas.py`); bağlam değişmiş |

Bu 25 görev engelli kalır; hiçbiri "completed" yapılmadı.

## Komutlar (ham çıktı `ahos_core/config/CLINE-KANIT.md`)

```text
python tools/unlock_blocked.py 20 --include-board --match sandbox-1793538772 --apply
python tools/drain_batch.py --limit 20
python tools/unlock_blocked.py 20 --include-board --match sandbox-1793538772   # 0 aday, 12 atlandı
python -m pytest -q tests/test_queue_repair.py                                 # 10 passed
```

## Sınır (iddia edilmeyen)

- Replay, görevin **içeriğini** iyileştirmez; yalnızca kuyruk durumu hatasını kaldırır.
- Üretilen belgeler deterministik şablon çıktısıdır; alan uzmanı derinliği iddiası yoktur.
- Kalan 25 görev ve 43 blocked satırın tamamı için "otomatik kurtarma" yoktur.
