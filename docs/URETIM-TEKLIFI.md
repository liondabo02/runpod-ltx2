# Tek sahne üretim teklifi — onay bekliyor

Tarih: 2026-11-07 · Sahne: **S01-PARK-KITE-001** · Süre: **6 sn** · 1920×1080 · 24 fps

> Durum: **üretim başlamadı.** Yerel GPU/model yok; ücretsiz görsel kademesi kapandı
> (HTTP 402). Tek eksik: **sağlayıcı anahtarı + harcama onayı**. Onaysız harcama
> yapılmayacak.

## 1. Ne üretilecek?

Aden (3) ve Kaan (1), yemyeşil parkta renkli bir uçurtmayla oynuyor; tek plan,
doğal hareket, sıcak sabah ışığı, sinematik 3D çocuk animasyonu görünümü.
Kanon: `characters/aden.json`, `characters/kaan.json`,
`characters/scenes/park-kite-01.json`.

## 2. Hat (onay sonrası)

```text
1. Keyframe (1920x1080)      görsel model — 2 aday
2. Süreklilik kontrolü       renk + oran + yüz (insan önizleme)
3. I2V                        LTX-2.5 Pro, 6 sn, 1080p — 3 aday + 1 yedek
4. Teknik QA                  tools/creative_qa.py  (ffprobe + kare ölçümü)
5. Yaratıcı QA                Harun: karakter/ hareket/ ışık/ estetik
6. Teslim                     MP4 + başlangıç/bitiş kareleri + manifest + rapor
```

Remotion yalnız 6. adımda (gerekirse başlık/renk/altyazı) kullanılır; karakter
hareketini üretmez (`docs/REMOTION-ENTEGRASYON.md`).

## 3. Maliyet (doğrulanmış fiyatlar)

LTX-2.5 resmî fiyatı (çıktı saniyesi): **Pro 1080p $0,17** · Fast 1080p $0,13
([docs.ltx.video/pricing](https://docs.ltx.video/pricing)).

| Kalem | Hesap | Tutar |
|---|---|---|
| LTX-2.5 Pro I2V, 6 sn, 1080p × 3 aday | 3 × 6 × $0,17 | **$3,06** |
| Yedek 1 çekim | 6 × $0,17 | $1,02 |
| **Bütçe tavanı** | | **$5,00** |
| Görsel keyframe | sağlayıcıya göre değişir | ayrı doğrulanacak |
| Remotion / ffmpeg / edge-tts | yerel | $0,00 |

Fiyatlar API listesinden; sağlayıcı faturası son sözü söyler. Tavan aşılırsa
üretim **durur**, yeni onay istenir.

## 4. Gerekli olan (Harun)

1. **Bir API anahtarı** — biri yeterli:
   - **Hugging Face tokeni (ücretsiz, önerilen):** `HF_TOKEN` — ZeroGPU kotasını açar,
     ücret yok, hesap yalnız ücretsiz kademe. Bugünkü engel tam olarak bu.
   - Lightricks/Venice LTX (`LTX_API_KEY` / `VENICE_API_KEY`), veya
   - fal.ai (`FAL_KEY`, LTX-2/2.5 barındırıyorsa), veya
   - RunPod (`RUNPOD_API_KEY` + LTX endpoint kimliği; repodaki Docker imajı).
2. **Harcama onayı:** yalnız ücretli sağlayıcı seçilirse; "LTX-2.5 Pro I2V, 4 çekime
   kadar, en fazla 5 USD" cümlesi. HF Space yolu **0 USD**.
3. Anahtar bu makinede **ortam değişkeni** olarak verilmeli; repoya yazılmaz.

## 4b. Ücretsiz yol (doğrulandı, kota bekliyor)

Resmî Hugging Face Spaces anahtarsız çalışıyor:

```powershell
python tools/ltx_space_render.py --keyframe deliverables/S01-PARK-KITE-001/keyframes/keyframe-seed-11-rgb.png --duration 5 --seed 101 --decoder diffusion --tag take1
python tools/finalize_scene.py --video deliverables/S01-PARK-KITE-001/park-kite-take1.mp4 --tag take1 --model "LTX-2.5 (HF Space)" --cost-usd 0
```

Bugün 2 keyframe + 2,04 sn smoke üretildi; 5 sn'lik çekim anonim ZeroGPU kotası
dolduğu için alınamadı (`docs/S01-DURUM.md`). `HF_TOKEN` verilirse aynı komut
tek çağrıda 5 sn'lik çekimi üretir.

## 5. Ön kabul kapıları

**Teknik (otomatik):** MP4 açılıyor; 6,0 ±0,2 sn; 1920×1080; 24 fps ±0,5;
144 ±5 kare; donma oranı ≤ %30; flicker ≤ 6/255; ses varsa 48 kHz.
"Teknik PASS" **yaratıcı PASS değildir**.

**Yaratıcı (Harun):**
1. Aden/Kaan yüz kimliği ilk ve son karede aynı.
2. Kıyafet renkleri kanonla uyumlu (ΔE ≤ 8).
3. Boy oranı 0,776 ± %5.
4. Hareket doğal; ağırlık aktarımı ve rüzgâr tepkisi inandırıcı.
5. Işık yönü/sıcaklığı sabit; gölge yönü değişmiyor.
6. Kompozisyon: çocuklar sol üçte bir, uçurtma sağ üst.
7. El/yüz/uzuv bozulması, titreme, zıplama yok.
8. Genel estetik: profesyonel 3D çocuk animasyonu; düz vektör/geometrik değil.

## 6. Teslim paketi

```text
deliverables/S01-PARK-KITE-001/
  park-kite.mp4            (git'e girmez)      gerçek I2V çıktısı
  start.png / end.png      (git'e girmez)      ilk/son kare
  manifest.json            (girer)             model, süre, seed, maliyet, hash
  qa-technical.json        (girer)             ölçümler
  KALITE-RAPORU.md         (girer)             teknik + yaratıcı ayrı
  characters/*.json        (girer)             kanon sürümü
```

## 7. Dürüst riskler

- 6 sn I2V'de bile yüz kayması/el bozulması olabilir; 3 aday bunun için.
- LTX-2.5 I2V "profesyonel" kaliteyi garanti etmez; ilk gerçek ölçüm olacak.
- Alternatif (Kling/Veo) fiyatı **doğrulanmadı**; gerekirse ayrı onay gerekir.
- Referans görselleri de ücretli görsel modeli gerektiriyor; ücretsiz kademe kapalı.

## 8. Onay metni (kopyala-yapıştır)

```text
Onay: LTX-2.5 Pro I2V, 6 sn, 1080p, en fazla 4 çekim, bütçe tavanı 5 USD.
Anahtar: <sağlayıcı> ortam değişkeni olarak verilecek.
```

## 9. Seçilen yol: RunPod (kendi GPU)

Karar: **RunPod + repo'nun LTX-2 worker imajı**. Gereken iki değer:

```text
RUNPOD_API_KEY=...
RUNPOD_LTX_ENDPOINT_ID=...
```

Bu iki satır repoya **yazılmaz**; `C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\.env.runtime`
dosyasına yazılır (`.gitignore`'da). Verildikten sonra:

```powershell
python tools/runpod_preflight.py --payload-preview
# "ready": true olmalı
```

Hazır olduğunda sıra:

1. `--ping` (GPU uyandırır; **ücretlidir**, açık onay ister) → worker'ın ayakta olduğunu doğrular.
2. Endpoint'in hangi modeli çalıştırdığını doğrula: **LTX-2 (19b) mi, LTX-2.5 mi?**
   Repo imajı LTX-2'ye hedefli; LTX-2.5 için imajın/modelin güncellenmesi gerekir.
3. Keyframe üretimi (görsel model) → I2V → MP4 → `tools/creative_qa.py` → Harun onayı.

**Üretim parametresi:** model girişi 1024×576 (16:9, 32'ye bölünebilir); teslim
1920×1080'e Lanczos ile ölçeklenir. 1080 doğrudan modele verilmez (32'ye bölünmez).

> Not: Bu adımlar anahtar gelmeden çalıştırılmaz. `tools/runpod_preflight.py`
> anahtarı yazdırmaz, ağ çağrısı yapmaz ve harcama başlatmaz.

