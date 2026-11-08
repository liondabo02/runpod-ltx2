# Aden referans incelemesi — QA (P2)

Durum: **NEEDS_REVISION** · sahip onayı yok · yeni görsel üretilmedi

## İncelenen dosyalar (orijinaller değiştirilmedi)

| Dosya | Tür | Teknik | SHA-256 |
|---|---|---|---|
| `deliverables/S01-PARK-KITE-001/keyframes/keyframe-girl-seed-77.png` | PNG | 1280×720, 760.222 bayt | `b62eb34a9278eb863acbc84ef8e90147e1fdafc2f0c2fe837ccdc60498cbafb0` |
| `deliverables/S01-PARK-KITE-001/park-kite-take2-girl-1080p.mp4` | MP4 | 1920×1080, H.264, 24 fps, 120 kare, 5,000 sn, 3.253.712 bayt | `1a66c89f5ffded000c24f075087b6d87673f58a2f91b805682e740d82f9aab08` |

Video, bilinen üretim kaydına göre **768×512 native** render'ın 2,5× Lanczos büyütmesidir;
gerçek 1080p değildir. 5 saniyelik teknik testtir, 30 saniyelik pilot değildir.

## Kanon karşılaştırması (görsel)

**Tutan:** Aden kız; kobalt mavi tişört + sarı uçurtma baskısı; lacivert şort; krem spor ayakkabı;
omuz hizası koyu kahve saç; Kaan mercan tişört; park/çimen/sabah ışığı uyumlu.

**Tutmayan / eksik:**
1. **Sarı yıldız toka görünmüyor** — Aden'in imza öğesi yok.
2. **Sol yanaktaki üç çil görünmüyor** — kimlik öğesi eksik.
3. Kaan **1 yaş bebeksi orandan uzak**, yaklaşık 1,5–2 yaş okunuyor.
4. Uçurtma kuyruğu **ince şerit**; altı büyük kumaş şeritten oluşan kanonik kuyruk değil.
5. Video upscale; yüz detayı 1080p native değil.

## Karar

- **Model sheet v2 yerine kullanılamaz.** Yalnız ışık/kompozisyon/park referansı olarak yararlı.
- Yeni yüz üretilmedi, mevcut yüz değiştirilmedi.
- Kimlik onayı **sahibe** aittir; otomatik APPROVED verilmedi.

## Kanıt

- `studio/qa/aden-reference-manifest.json` (hash + teknik)
- `studio/qa/evidence/aden-take2-frame-2s.png` (videodan alınmış 960×540 önizleme)
- `studio/qa/aden-preview.html`
