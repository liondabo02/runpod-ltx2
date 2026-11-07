# S01-PARK-KITE-001 — tek sahne durumu

Tarih: 2026-11-07 · Sahne: Aden (3) + Kaan (1), parkta uçurtma · Hedef: 5–8 sn, 1080p

> **Durum: üretim yarıda.** Gerçek LTX-2.5 hattı çalıştı; 5 sn'lik çekim, ücretsiz
> ZeroGPU kotası dolduğu için tamamlanamadı. Ücret harcanmadı, hesap açılmadı.

## 1. Çalışan hat (doğrulandı)

| Adım | Sağlayıcı | Sonuç |
|---|---|---|
| Keyframe | `black-forest-labs/FLUX.1-schnell` (HF Space) | **2 görsel**, 1280×720, seed 11 / 22, 6–13 sn |
| I2V smoke | `Lightricks/LTX-2.5` (HF Space, resmî) | **2,04 sn MP4**, seed 42, **18,4 sn** |
| I2V 5 sn | aynı | **engellendi**: ZeroGPU kotası |

Kanıt dosyaları:
- `deliverables/S01-PARK-KITE-001/keyframes/keyframe-seed-11.png` (WebP; `-rgb.png` dönüşümü)
- `deliverables/S01-PARK-KITE-001/keyframes/keyframe-seed-22.png`
- `deliverables/S01-PARK-KITE-001/smoke-ltx25-2s.mp4` (girdi eski poster; sadece hat testi)
- `deliverables/S01-PARK-KITE-001/run-take1.json` (kota engeli manifesti)

## 2. Keyframe değerlendirmesi (yaratıcı ön bakış)

**seed-11 (aday):** kompozisyon doğru (çocuklar solda, uçurtma sağ üst), sıcak sabah
ışığı, sığ alan derinliği, 3D çocuk animasyonu hissi güçlü. Eksik: **Kaan 1 yaşında
gibi durmuyor**; iki kardeş neredeyse akran görünüyor, boy oranı 0,776 değil.
**seed-22:** uçurtma Kaan'ın kafasına "şapka" olmuş, köşede ikinci uçurtma var — elenir.

Bu haliyle keyframe **yaratıcı kabul için yeterli değil**; Kaan'ı bebekleştiren bir
revizyon (daha güçlü prompt + yeni seed) gerekiyor.

## 3. Engelin tam adı

```text
Provider A: Hugging Face ZeroGPU (anonim)
Hata: "You have exceeded your ZeroGPU runs limit." / "0s left"
Tüketim: 3 çalıştırma (2 FLUX + 1 LTX smoke)
Çözüm A: ücretsiz HF hesabı tokeni → HF_TOKEN (ücret yok, kota açılır)
Çözüm B: günlük kotanın sıfırlanmasını beklemek

Provider B: RunPod LTX endpoint
Kimlik: control_plane_v2/.env.runtime içinde RUNPOD_API_KEY + RUNPOD_LTX2_ENDPOINT_ID
        (endpoint dnwqoolyprqr69) — preflight artık bunları buluyor, "ready": true.
Engel 1: api.runpod.ai bu makineden yanıt vermiyor (istekler asılı kalıyor).
Engel 2: LB alt alanı (dnwqoolyprqr69.api.runpod.ai) yalnız 401/400 dönüyor:
         "not allowed for QB API, load balancer endpoint"; /run, /runsync,
         /generate, /v1/video/generate, /predict yolları aynı hatayı verdi.
Sonuç: onay verilmesine rağmen (≤$1.50) bu makineden RunPod çağrısı YAPILAMADI;
       ücret harcanmadı.
```

Teknik olarak istenen 5 sn'lik çekim **bir çağrı** ile alınabilir; LTX-2.5 Space'te
süre sınırı **5,0 sn** (6 sn istemek "maximum 5.0" hatası verir). 5 sn, hedefin
(5–8 sn) alt sınırı içindedir.

## 4. Üretim komutu (kota açılınca)

```powershell
# 1) keyframe revizyonu (Kaan'ı bebekleştir)
python tools/ltx_space_render.py --generate-keyframe --seed 41

# 2) 5 sn I2V
python tools/ltx_space_render.py --keyframe deliverables/S01-PARK-KITE-001/keyframes/keyframe-seed-41.png --duration 5 --seed 101 --decoder diffusion --tag take1

# 3) 1080p teslim paketi + teknik QA
python tools/finalize_scene.py --video deliverables/S01-PARK-KITE-001/park-kite-take1.mp4 --tag take1 --model "LTX-2.5 (HF Space)" --cost-usd 0
```

`tools/finalize_scene.py` başlangıç/bitiş karelerini, `manifest.json`, `qa-technical.json`
ve `KALITE-RAPORU.md` dosyalarını üretir; **yaratıcı PASS vermez**.

## 5. Kabul durumu

| Kapı | Durum |
|---|---|
| Teknik (MP4, 5 sn, 1080p, 24 fps, donma/titreme) | **bekliyor** (çekim yok) |
| Yaratıcı (karakter, hareket, ışık, estetik) | **NOT_EVALUATED** — Harun |
| Maliyet | **0,00 USD** (ücretsiz kademe) |

## 6. Dürüst not

Bu turda "profesyonel çizgi film" **teslim edilmedi**. Teslim edilen: çalışan gerçek
LTX-2.5 hattı, iki keyframe adayı, teknik QA ve teslim paketi araçları. Eksik olan
tek şey kotadır; kalite iddiası değil, ölçüm ve onay vardır.
