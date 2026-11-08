# Sıfır maliyetli görsel üretim alternatifleri — araştırma

Tarih: 2026-11-08 · Kapsam: Aden turnaround v2 için kimlik koruyan, ücretsiz yol
Durum: **hiçbir alternatif üretime hazır değil**; ücretli servis/abonelik kullanılmadı.

## 1. Bilinen engel

- HF ZeroGPU kotası kapalı: `zerogpu_quota`, exit 3. Aynı istek tekrarlanmadı.
- Ücretli API / PRO aboneliği yasak; kullanılmadı.

## 2. Bu makinede ölçülen gerçekler

| Kontrol | Komut | Sonuç |
|---|---|---|
| GPU | `nvidia-smi` | **yok** (komut bulunamadı) |
| Torch | `torch.__version__`, `torch.cuda.is_available()` | **2.8.0+cpu**, CUDA **False**, 0 cihaz, 8 CPU thread |
| ComfyUI / SD WebUI | klasör taraması | **yok** |
| HF önbelleği | `~/.cache/huggingface/hub` | yalnız `zeroscope_v2_576w` (video) ve `Kokoro-82M` (TTS); **SDXL/Kontext/IP-Adapter yok** |
| Pollinations | `GET /models` | HTTP 200, model listesi **`["sana"]`** (metinden görsele) |

## 3. Değerlendirilen alternatifler

| Alternatif | Maliyet | Kimlik koruma | Durum |
|---|---|---|---|
| HF ZeroGPU (Kontext) | 0 | Evet | **Kapalı** (kota) |
| Pollinations | 0 | **Hayır** — yalnız metin istemi, referans görsel parametresi yok | Çalışıyor ama işe yaramaz |
| HF Inference Providers (Kontext) | Ücretli kota | Evet | **Kullanılmadı** (ücret) |
| Yerel diffusers (CPU) | 0 yazılım | Kuramsal olarak IP-Adapter ile | **Hazır değil**: model ağırlığı yok, CPU'da süre ölçülmedi, kimlik testi yok |
| ComfyUI + SDXL/IP-Adapter | 0 yazılım | Evet (kurulumla) | **Kurulu değil**; yeni altyapı demek |
| Mevcut 2D keyframe'den cutout | 0 | Evet (aynı pikseller) | Yalnız animasyon; yeni açı/model sheet üretmez |
| Bulut ücretsiz GPU (Kaggle/Colab) | 0 | Evet | **Yeni hesap** gerekir; yasak |

## 4. Neden "hazır" değil?

- Pollinations yalnız `sana` metinden görsele modeli sunuyor; referans görsel/kontext
  parametresi yok. Aden'in yüzünü, saçını ve kıyafetini koruyamaz.
- Yerel CPU hattı için SDXL + IP-Adapter indirmek gerekir (~7 GB); tek görselde
  süre ve kimlik tutarlılığı **ölçülmedi**. Ölçülmeden "hazır" denemez.
- Ücretsiz kota dışındaki Kontext yolları ücretli sağlayıcıya çıkar.

## 5. Sonuç ve öneri

Şu anda **kanıtlanmış, sıfır maliyetli, kimlik koruyan** bir görsel üretim yolu yok.
Aden turnaround v2 üretilmedi; sahte/benzer bir görsel "v2" diye sunulmayacak.

Seçenekler (sahip kararı):
1. Ücretsiz ZeroGPU kotasının açılmasını bekle (maliyet 0).
2. Yerel CPU + IP-Adapter hattını **deneme** olarak kur; önce tek görselde süre/kimlik
   ölçümü yap, sonuç tatmin ediciyse devam et (yeni ağırlık indirmesi gerekir).
3. Onaylı bütçeyle ücretli Kontext (şu an yasak).

## 6. Yapılmayanlar

Görsel üretimi, ücretli çağrı, yeni hesap, yeni ajan/panel/altyapı, özel medya yükleme.
