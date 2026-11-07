# Kuyruk güvenliği ve kurtarma raporu — 2026-11-07

Kaynak: canlı DB `ahos_core/runtime/company-service.db` (salt okunur doğrulama)
Dal: `feature/ahos-queue-reliability` · Worktree: `C:\actions-runner\_work\AHOS-QUEUE-RELIABILITY`

## 1. Canlı veri (yeniden doğrulandı)

```text
completed 4028 · blocked 43 · failed 14 · cancelled 1378 · pending 0
pragma integrity_check -> ok · quick_check -> ok
```

## 2. Yedek

SQLite backup API ile tutarlı kopya (WAL dahil):

```text
C:\actions-runner\_work\AHOS_BACKUPS\company-service-queue-reliability-20261107T221921.db
8.093.696 bayt · integrity ok · quick ok
```

## 3. Engelli/hata sınıfları (57)

| Sınıf | Adet | Tekrar güvenli mi? |
|---|---|---|
| `board_schema` | 37 | Pano geçerli; ama görev bağlamı aşağıda |
| `code_validation` | 11 | Hayır — yürütücü/kod hatası; kod düzeltmesi gerekir |
| `qa_failed` | 7 | Hayır — gerçek QA başarısızlığı |
| `lease` | 1 | Teknik olarak evet; ama kriz kopyası |
| `pilot` | 1 | Hayır — tarihsel pilot kalıntısı |

## 4. Dry-run (canlıya yazmadan)

```text
board_valid -> (True, 'ok')
lock-only   -> 0 aday
with-board  -> 25 aday (hepsi board_schema) + 12 zaten kurtarılmış (atlandı)
```

25 adayın seçim matrisi:

| Grup | Adet | Karar | Gerekçe |
|---|---|---|---|
| `*-crisis-*` kopyaları | 20 | **Replay yok** | Aynı kök nedenin yinelenen kopyası; tek görevle izlenir |
| `CMD-sales-arge-*` | 2 | **Replay yok** | Aynı sınıfta 7+ tamamlanmış halef var; kopya üretir |
| `CMD-software-ahos-ideas-py-*` | 3 | **Replay yok** | Hedef dosya güncel proje kökünde yok (bağlam değişti) |
| 12 sandbox `-1793538772` | 12 | **Zaten kurtarıldı** | `-r2` çocukları completed; idempotent guard atladı |

**Canlı replay: 0.** "Yalnız gerçekten geçerli, yararlı ve güvenli" koşulunu sağlayan
aday yok; hiçbir görev zorla çalıştırılmadı, hiçbir engelli satır "completed" yapılmadı.

## 5. Kapasite ve sınırlar

- Pending: **0** · tavan **300** (`MAX_PENDING_MISSIONS`), güvenli yeniden üretim eşiği **240**.
- Bu turda yeni görev üretilmedi; pending 0 kaldı.
- Önceki 12 kurtarma (`-r2`) completed + `delivery.verified=1` durumunu koruyor;
  yeniden üretilmedi.

## 6. Maliyet

**0 USD.** Model/API çağrısı yapılmadı; yalnız SQLite okuma, dry-run ve yerel testler.
