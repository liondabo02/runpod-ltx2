# S01-PARK-KITE-001 — tek sahne durumu

Tarih: 2026-11-07 · Sahne: Aden (3) + Kaan (1), parkta uçurtma · Hedef: 5–8 sn

> **Durum: iki gerçek çekim var.** take1 (erkek Aden, kamera kayması) elendi;
> **take2-girl** doğru kanonla (kız Aden), sabit kamera ve iki çocuk kadrajda üretildi.
> Teknik QA **PASS**; yaratıcı onay **Harun'da** (NOT_EVALUATED). Ücret: **0,00 USD**.
>
> **Kanon uyarısı:** take1, Aden **erkek** promptuyla üretildi. Doğru kanon Aden'in
> **kız** olduğudur (`core_cast_voice_catalog`: girl). Bu yüzden take1 geçerli
> referans değildir; yeni çekimler kız Aden kanonuyla yapılır.

## 0. Take2-girl (güncel çekim)

| Alan | Değer |
|---|---|
| Dosya | `park-kite-take2-girl-raw.mp4` (454.310 bayt) · teslim `park-kite-take2-girl-1080p.mp4` |
| Model | LTX-2.5 (HF Space), I2V, `decoder=conv` |
| Doğal çıktı | **768×512**, 121 kare, 24 fps, **5,04 sn** · seed 303 |
| Keyframe | `keyframes/keyframe-girl-seed-77.png` (1280×720, FLUX; kız Aden) |
| Upscale | 2,5× → 1920×1080 (Lanczos) — **doğal 1080p değil** |
| Teknik QA | PASS: freeze 0,008 · flicker 0,13 · 5,022 sn · sharpness 8,2 |
| Yaratıcı | **NOT_EVALUATED** — Harun; kamera sabit, iki çocuk 0–5 sn kadrajda |

Gözlenen güçlü yanlar: kimlik sürekliliği (kız Aden + Kaan), sabit kamera, yumuşak
sabah ışığı, uçurtma kompozisyonu. Zayıf yanlar: 768×512 + upscale nedeniyle
yumuşaklık; sahne çok parlak (mean luma 182); hareket enerjisi düşük (1,88).

## 1. Üretilen gerçek çıktı

| Alan | Değer |
|---|---|
| Dosya | `deliverables/S01-PARK-KITE-001/park-kite-take1-raw.mp4` (698.760 bayt) |
| Teslim (upscale) | `park-kite-take1-1080p.mp4` (5.302.165 bayt) |
| Model | `Lightricks/LTX-2.5` (HF Space, image-to-video, `decoder=conv`) |
| Doğal çözünürlük | **768×512**, 121 kare, 24 fps, **5,04 sn** |
| Upscale | 2,5× → 1920×1080 (Lanczos). **Doğal 1080p değildir.** |
| Seed | 101 · prompt: sabit kare, iki kardeş, uçurtma sağ üst |
| Süre / maliyet | 32,6 sn üretim · **0 USD** |
| SHA-256 (teslim) | `d3f1d16052597e33…` (manifest tam hash) |

Yan dosyalar: `park-kite-take1-start.png`, `park-kite-take1-end.png`,
`manifest.json`, `qa-technical.json`, `KALITE-RAPORU.md`.

## 2. Teknik QA (otomatik) — PASS

```text
1920x1080 · 24 fps · 5,022 sn · 120 kare tarandı
motion_energy            = 12,13
changed_pixel_ratio_mean = 0,381   (kare başına %38 piksel değişimi)
freeze_ratio             = 0,008   -> PASS
flicker_luma_delta       = 0,964   -> PASS
sharpness_laplacian      = 9,22    (düşük: 2,5× upscale)
creative                 = NOT_EVALUATED
```

Teknik PASS yalnız "dosya oynuyor, donmuş değil" demektir; **kalite onayı değildir**.

## 3. Yaratıcı QA (insan) — RED

| Kontrol | Sonuç | Gerekçe |
|---|---|---|
| Karakter sürekliliği | ☒ | 0–1,5 sn iki kardeş net; sonra kamera yukarı kayıyor |
| Kompozisyon | ☒ | 2,5 sn'de çocuklar kadrajın dışına çıkıyor; 4,9 sn'de yalnız uçurtma var |
| Kaan'ın yaşı/oranı | ☒ | Keyframe'de 1 yaş görünümü zayıf; boy oranı 0,776 değil |
| Hareket doğallığı | ◐ | Kumaş/ip hareketi iyi; karakter hareketi kısa |
| Işık/atmosfer | ☑ | Sıcak sabah ışığı, bokeh, renk paleti güçlü |
| Görsel bozulma | ☑ | Yüz/el erimesi, titreme yok |
| Estetik | ◐ | 3D çocuk animasyonu hissi iyi; 768×512 + upscale yumuşak |

**Karar: take1 teslim edilemez.** Prompt "uçurtma sağ üste tırmanır" dediği için model
kamerayı gökyüzüne taşımış; "sabit kamera, çocuklar kadrajda kalır" vurgusu take2'de
güçlendirildi ama **kota** nedeniyle üretilemedi.

## 4. Keyframe denemeleri

- **seed-11 (take1 girdisi):** iki kardeş, mavi/mercan tişört, uçurtma sağ üst, sıcak ışık.
  Kusur: Kaan 1 yaş gibi değil, boy farkı küçük.
- **seed-41 (baby-focus prompt):** üçüncü bir çocuk uydurdu, tişörtlerde logo, saç/ten
  kanonu kaydı → **elenir**.
- **seed-22:** uçurtma Kaan'ın başında "şapka", ikinci uçurtma → **elenir**.

## 5. Kalan tek engel

```text
Hugging Face ZeroGPU (anonim): "You have exceeded your ZeroGPU runs limit."
- take1 kotayı tüketti; take2 (sabit kamera) bu yüzden alınamadı.
- Çözüm: ücretsiz HF hesabı tokeni (HF_TOKEN) → ek çalıştırma kotası, ücret yok.
- Alternatif: kota sıfırlanmasını beklemek.
- RunPod: kimlik var (dnwqoolyprqr69) ama api.runpod.ai bu makineden yanıt vermiyor;
  LB yolu "not allowed for QB API" döndürüyor. Onay (≤$1.50) kullanılamadı, harcama 0.
```

## 6. Sonraki tek komut (kota açılınca)

```powershell
# take2: sabit kamera + iki çocuk kadrajda
python tools/ltx_space_render.py --keyframe deliverables/S01-PARK-KITE-001/keyframes/keyframe-seed-11-rgb.png --duration 5 --seed 202 --decoder conv --tag take2
python tools/finalize_scene.py --video deliverables/S01-PARK-KITE-001/park-kite-take2-raw.mp4 --tag take2 --seconds 5 --model "LTX-2.5 (HF Space)" --workflow "image-to-video /run; conv; native 768x512; seed 202" --cost-usd 0
```

## 7. Dürüst not

Profesyonel sahne **henüz teslim edilmedi**. Ancak artık gerçek bir model çıktısı,
ölçülmüş teknik rapor ve somut yaratıcı ret gerekçesi var. Sorun araç değil, **kota**;
kota açıldığında take2 ve varyasyonları aynı hatla üretilebilir.
