# S01E001 — “Uçurtmanın Kayıp Kuyruğu” üretim paketi

Durum: **DRAFT_FOR_OWNER_APPROVAL** · 8 dakikalık taslak senaryo + ilk 30 sn çekim listesi + ses envanteri.

| Dosya | İçerik |
|---|---|
| `episode.json` | 12 sahne, tam **480 sn**, 38 replik, davranış etiketleri |
| `SENARYO-TR.md` | Okunabilir Türkçe senaryo |
| `shotlist-30s.json` | 6 çekim × 5 sn = **30 sn**, kamera/hareket/duygu/konum/ses/süreklilik |
| `CEKIM-LISTESI-30SN.md` | Çekim listesinin okunabilir hâli |
| `voice-inventory.json` / `SES-ENVANTERI.md` | Gerçek ses ölçümü; onay **NOT_EVALUATED** |
| `URETIM-HAZIRLIGI.md` | Mevcut paket incelemesi, yeniden kullanım, engeller |
| `evidence/` | Doğrulayıcı ve test çıktıları |

## Doğrulama

```powershell
python tools/validate_s01e001.py --json
python -m pytest -q ahos_core/tests/test_s01e001_package.py
```

Beklenen: süre 480/30, Kaan ≤2 kelime, Aden kız/3 yaş, Kaan erkek/1 yaş, 6 test PASS.

## Sınırlar

- Bu bir **taslaktır**; sahip onayı olmadan final değildir.
- Görsel üretim yok; ZeroGPU kotası kapalı. Kota açılınca yalnız Aden turnaround v2.
- Ses dosyaları jenerik referanstır; bölüm replikleri seslendirilmedi.
