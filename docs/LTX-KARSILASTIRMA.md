# LTX hattı: mevcut durum vs LTX-2.5 ve alternatifler

Tarih: 2026-11-07 · Amaç: 6–8 sn, 1080p, tek sahne için doğru modeli ve gerçek
maliyeti **doğrulanmış** kaynaklarla seçmek. Doğrulanmayan fiyat "tahmini" olarak
işaretlendi; hiçbir sağlayıcı kullanılabilir ilan edilmedi.

## 1. Repodaki hat (LTX-2)

- Hedef: `ltx-2-19b-distilled-fp8` + Gemma text encoder + IC-LoRA + upscaler'lar
  (`README.md` ortam değişkenleri).
- Çalışma yolu: RunPod GPU → Docker (`ghcr.io/tolgasci/runpod-ltx2`) → ComfyUI →
  `workflows/image_to_video.json` → MP4.
- Durum: **çalışmıyor** — GPU yok, ComfyUI kapalı, ağırlık yok, `RUNPOD_API_KEY` yok,
  LTX endpoint kimliği yok (`docs/MEDYA-DENETIM.md`).
- Ayrıca: LTX-2, LTX-2.5 çıkışıyla **deprecated** edildi; API tarafında Ağustos 2026
  sonrası kaldırıldığı belirtiliyor ([llm-stats LTX-2.5](https://llm-stats.com/blog/research/ltx-2.5-launch)).
  Yani repoyu birebir kurmak, eski modele yatırım olur.

## 2. LTX-2.5 (Ağustos 2026)

| Özellik | Değer |
|---|---|
| Sürüm | LTX-2.5 Fast / Pro, ~11 Ağustos 2026 |
| Modlar | text→video, image→video (I2V), video→video; ses opsiyonel |
| Süre | Fast 6–20 sn (2 sn adım), Pro 6/8/10 sn |
| Çözünürlük | Fast 720p/1080p/2K/4K · Pro 720p/1080p |
| Yeni | native multi-shot, yeni diffusion video decoder, Gemma 4 12B TE |
| Ağırlıklar | açık (`Lightricks/LTX-2.5`), Community lisansı (<10M $ ARR ücretsiz) |
| Kendi barındırma | ~16 GB VRAM sınıfı iddiası; bizim makinede GPU yok, disk 30 GB |

**API fiyatı (çıktı saniyesi başına, resmî doküman):**

| Model | 720p | 1080p | 2K | 4K |
|---|---|---|---|---|
| `ltx-2.5-fast` | $0,09 | $0,13 | $0,19 | $0,30 |
| `ltx-2.5-pro` | $0,12 | $0,17 | — | — |

Kaynak: [docs.ltx.video/pricing](https://docs.ltx.video/pricing) (aktaran
[llm-stats](https://llm-stats.com/blog/research/ltx-2.5-launch)). Venice API'de
Fast I2V "from $0,0989/sn" olarak listeli
([Venice docs](https://docs.venice.ai/models/ltx-video-2-5-fast)).

**Tek sahne için maliyet:**

| Senaryo | Hesap | Tek çekim | 4 çekim (en kötü) |
|---|---|---|---|
| LTX-2.5 **Pro** I2V, 6 sn, 1080p | 6 × $0,17 | **$1,02** | **$4,08** |
| LTX-2.5 **Fast** I2V, 8 sn, 1080p | 8 × $0,13 | **$1,04** | **$4,16** |
| LTX-2.5 Fast I2V, 6 sn, 720p | 6 × $0,09 | $0,54 | $2,16 |

Öneri: **Pro 1080p 6 sn**, 3–4 aday çekim; bütçe tavanı **5 $**.

## 3. Alternatifler (fiyat doğrulanmadı — kullanılabilir sayılmadı)

fal.ai kataloğunda Kling 3.0 / 2.5, Veo 3.1, Seedance 2.5, Wan 3.0, MiniMax H3,
LTX 2.3 listeli ([fal video modelleri](https://fal.ai/models/fal-ai/kling-video/v2.5-turbo/standard/image-to-video)).
Bu sayfalar fiyatı dinamik yüklüyor; **doğrulanmadan** karşılaştırmaya sokulmadı.
Karakter sürekliliği için üstün oldukları iddia edilmiyor; gerekirse ayrı ölçüm gerekir.

Kiralık GPU (RunPod) seçeneği: repo'nun önerdiği A100 80GB / H100 sınıfı GPU + 150 GB
disk + model indirme gerekir. Bu makinede 30 GB boş disk ve GPU yok; dolayısıyla
yalnız uzak GPU ile mümkün. Saatlik ücret sipariş anında doğrulanmalı (bu raporda
doğrulanmadı).

## 4. Karar

1. **Birincil yol:** LTX-2.5 **Pro** I2V, 6 sn, 1080p, tek sahne; 3 aday + 1 yedek.
2. **Gerekli ön koşul:** sağlayıcı API anahtarı (Lightricks/Venice/fal) **veya**
   RunPod anahtarı + LTX endpoint. Bugün hiçbiri yok.
3. **Anahtar gelmeden üretim yok.** Onaysız harcama yapılmayacak.
4. LTX-2.5 çıktısı da otomatik "profesyonel" sayılmaz: teknik QA + yaratıcı QA ayrı
   yürütülür, son onay Harun'a aittir (`docs/URETIM-TEKLIFI.md`).
