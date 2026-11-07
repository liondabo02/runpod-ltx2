# AHOS — Profesyonel çizgi film hattı: denetim raporu

Tarih: 2026-11-07 · Repo: `C:\actions-runner\_work\runpod-ltx2\runpod-ltx2`
Dal: `feature/agent-control-plane` · Kural: repo, hafıza veya mevcut medya **silinmedi**.

Bu rapor yalnız **ölçülen** durumu yazar. "Kullanılabilir" demek için erişim ve
maliyet ayrıca doğrulanır; doğrulanmayan hiçbir sağlayıcı kullanılabilir sayılmadı.

## 1. Yerel makine

| Kontrol | Komut | Ham sonuç | Yorum |
|---|---|---|---|
| GPU | `nvidia-smi` | bulunamadı | CUDA aygıtı yok |
| Torch | `python -c "import torch; ..."` | `torch 2.8.0+cpu cuda False` | CPU-only |
| FFmpeg | `ffmpeg -version` | `N-55702-g920046a` | var, montaj/ölçüm için yeterli |
| FFprobe | `ffprobe` | var | teknik QA için |
| Boş disk | `Get-PSDrive C` | **30,2 GB** | LTX-2.5 ağırlıkları (~40+ GB) sığmaz |
| Python medya | — | `cv2, numpy, PIL, moviepy, imageio` var | ölçüm/previz için yeterli |
| ComfyUI | `curl http://127.0.0.1:8188/system_stats` | `HTTP:000`, curl exit **7** | çalışmıyor |
| Yerel model | `git ls-files | *.safetensors/*.ckpt/*.gguf` | **0** | ağırlık yok |
| Runtime model dizini | `ahos_core/runtime/*model*` | yok | indirilmiş model yok |

**Sonuç:** Bu makinede gerçek video modeli **çalıştırılamaz**. CPU'da 22B sınıfı bir
video modeli 6 saniyelik 1080p sahne için pratik değildir (saatler/günler).

## 2. Repo ve mevcut LTX hattı

- Repo bir **RunPod Docker** projesidir: `README.md` → "Production odaklı LTX-2 + ComfyUI + RunPod pipeline".
- `workflows/image_to_video.json` (391 KB) ve `cinematic_i2v.json` (89 KB): ComfyUI-LTXVideo
  resmî örnek grafiklerinin kopyaları (README §Repo yapısı).
- `workflows/ltx2_text2video.json` **gerçek LTX video grafı değildir**; kendi README'si
  "Bu şablon ... gerçek LTX2 video grafı değildir" diyor. Önceki kabul belgesi de
  (`workflows/ltx2_render_acceptance_20261105.md`) "ComfyUI gerçek render ÇALIŞTIRILMADI" yazıyor.
- `ahos_core/ahos/runpod_ltx2.py`: gerçek, korumalı bir RunPod Serverless istemcisi.
  Üç ücret kapısı istiyor: `owner_approved`, `execution_enabled`, `paid_provider_enabled`.
  API anahtarını yalnız `RUNPOD_API_KEY` ortam değişkeninden okur.
- `ahos_core/ahos/studio_pipeline.py`: mevcut çizgi film hattı **2D vektörel** (PIL + ffmpeg +
  edge-tts). `docs/STUDIO.md` "sinematik AI video katmanı RunPod anahtarına bağlıdır" diyor.

## 3. Erişim / kimlik bilgileri

| Kontrol | Sonuç |
|---|---|
| `.env` / `.env.runtime` | **yok** (yalnız `.env.example` var) |
| `RUNPOD_API_KEY` | **tanımlı değil** |
| LTX endpoint kimliği | **tanımlı değil** (yalnız `RUNPOD_QWEN3_VOICE_DESIGN_ENDPOINT_ID` var) |
| Ollama tüneli `127.0.0.1:11500` | `curl exit 7` — tünel kapalı |
| FAL / Replicate / Lightricks anahtarı | **yok** |
| GitHub push | `git push --dry-run` → **başarılı** (`ae37276..9e372b5`) |

Yani ücretli model çağrısı bugün **teknik olarak da mümkün değil**: anahtar yok.
Onay verilse bile önce bir sağlayıcı anahtarının (ör. `FAL_KEY`, `LTX_API_KEY`,
`RUNPOD_API_KEY`) sağlanması gerekir.

## 4. Ücretsiz görsel üretim denemesi (referans için)

Tek anahtarsız seçenek Pollinations (Flux) idi:

```text
GET image.pollinations.ai/prompt/...  512x512           -> HTTP 200 (ilk istek, 3,8 sn)
GET ...?model=flux                                     -> HTTP 402
GET ...?enhance=true                                   -> HTTP 402
GET ...?width=1024&height=1024                         -> HTTP 402
GET ... 512x512 (birkaç istek sonra)                   -> HTTP 402
```

**Sonuç:** ücretsiz kademe kota sonrası kapandı (402 Payment Required). Bu yüzden
karakter referans görselleri de ücretsiz üretilemedi; ücretli/anahtarlı görsel
modeli gerekiyor. (Bu bir hata değil, bugünkü erişim durumudur.)

## 5. Mevcut 34 sn pilotun teknik ölçümü

`tools/creative_qa.py` (bu turda eklendi) ile:

```text
1920x1080, 24 fps, h264 + aac 48 kHz, 34,022 sn
motion_energy            = 0,159   (0-255 ölçeğinde ortalama kare farkı)
changed_pixel_ratio_mean = 0,0005  (kare başına değişen piksel: %0,05)
freeze_ratio             = 0,995   (600 karenin %99,5'i "donmuş" eşiğinin altında)
flicker                  = 0,106   -> PASS
creative                 = NOT_EVALUATED (insan onayı)
```

Eşik repo standardıyla aynı: bir karede değişen piksel oranı **%0,2'nin altındaysa
donmuş** sayılır (`docs/STUDIO.md` §3). Buna göre pilotun neredeyse tamamı donmuş
karelere yakın; "dosya oynuyor" teknik bir gerçektir, animasyon değildir.

Bu ölçüm, kullanıcının "yaratıcı kalite kabul edilmedi" kararıyla **teknik olarak
tutarlıdır**: video akmıyor, büyük ölçüde az hareketli karelerden oluşuyor.
Not: eşik sabit olduğu için çok yavaş ama gerçek animasyon da "donmuş" sayılabilir;
bu yüzden yaratıcı karar yine insana bırakıldı.

## 6. Tek cümlelik teşhis

Yerel makinede **GPU, model, ComfyUI ve API anahtarı yok**; bu yüzden profesyonel
3D çocuk animasyonu üretecek hat bugün **kapalı**. Eksik olan araç:
**GPU'lu barındırılmış bir video modeli (LTX-2.5 I2V) veya kiralık GPU + model indirmesi**.
