# AHOS-DELIVERY-001 — Teslim Raporu (Aden pilot)

## ÜRÜN

| Dosya | Boyut | SHA-256 |
|---|---|---|
| `deliverables/ADEN-PILOT-001/aden-pilot.mp4` | 1.746.064 bayt | `7e89b17e7a27f749c17a4e93b0a0553793e099ec25ac436d2d3744eed2bd2fde` |
| `deliverables/ADEN-PILOT-001/aden-pilot-de.mp4` | 1.746.503 bayt | `10cafb441f7d48a6f48d932fe42746e81d21644bd6ce192fe04ae113e00596c0` |
| `poster.png` | 25.342 bayt | manifestte |
| `subtitles-tr.srt` / `subtitles-de.srt` | 301 / 324 bayt | manifestte |
| `manifest.json` | 7.025 bayt | tüm kanıtlar |

- Çözünürlük **1920×1080**, **24 FPS**, süre **34,022 sn**, video **h264**, ses **aac 48 kHz stereo**.
- Türkçe anlatım + Almanca seslendirme (edge-tts, ücretsiz), ayrı TR/DE altyazı.
- Poster gerçek kareden üretildi.

## KALİTE

Bağımsız QA (`qa-01`, üreticiden ayrı) — tüm kontroller **true**:
`exists, video_stream, audio_stream, duration_ok, resolution_ok, fps_ok, frames_ok,
not_blank, audio_not_silent` · ses RMS **−22,93 dB** · kare std **35,78** (boş değil).

Sahne denetimi (kare çıkarımı): 2. sn uçurtma kuyruğu sağlam → 12. sn kuyruk kopmuş,
parçalar düşüyor → 24/32. sn renkli yeni kuyruk ve kumaş parçaları. Karakterler ve
arka plan üç sahnede tutarlı.

**Dürüst sınır:** Bu, **deterministik vektörel animasyon** (PIL + ffmpeg + edge-tts).
LTX-2/ComfyUI model çıktısı **değildir**; profesyonel stüdyo kalitesi iddia edilmez.
Yerel GPU yok (`nvidia-smi` yok), model dosyası yok (`docs/URETIM-DURUM.md`).

## İŞÇİLER (gerçek yürütülen görevler)

`project_run` ile creative→software→quality hattı; her görev `task_id`, worker,
çıktı yolu ve bağımsız `qa-01` doğrulaması taşır (`manifest.contributors`).

| Görev | Departman | Worker | Çıktı | QA |
|---|---|---|---|---|
| senaryo | creative | `creative-story-specialist` | `script-tr.txt` | qa-01 ✓ |
| kareler | creative | `creative-animation-specialist` | `frames/` (816 PNG) | qa-01 ✓ |
| ses | creative | `creative-audio-lead` (router aday bulamadı → yedek) | `audio-tr.wav` | qa-01 ✓ |
| mux | software | `data-01` (router seçimi) | `aden-pilot.mp4` | qa-01 ✓ |

`preflight` (gerçek görev öncesi): `assess_task → proceed`, `build_plans` → seçilen
**deterministik_yerel** (risk 0.1, başarı 0.95, maliyet 0); RunPod LTX alternatifi
risk/maliyet nedeniyle seçilmedi. Uzman yönlendirme gerçek görevde kullanıldı.

**Dürüst sınır:** Yürütücüler deterministik araçlardır; işçi kimlikleri rol atamasıdır,
LLM işçi bilişi çalıştırılmadı. Bu yüzden “iki departmanın gerçek bilişsel katkısı”
kriteri **kısmen** karşılanır (creative+software+quality rol/QA zinciri var).

## MALİYET

**0,00 USD.** GPU/API çağrısı yok; yalnız yerel PIL/ffmpeg ve ücretsiz edge-tts.
Ücretli RunPod/LTX-2 için Harun onayı gerekir (talep edilmedi).

## TESTLER

- `test_media_delivery.py` + `test_v4_dashboard.py`: **5 passed**, exit 0.
- Derleme: `py_compile` media_delivery/delivery_pilot/intelligence → exit 0.
- V4 final paketi: `tools/acceptance_v4.py` → PASS=20 FAIL=0 (önceki tur; hat değişikliği sonrası tekrar çalıştırılacak).

## GITHUB

Commit ve uzak hash push sonrası `git rev-parse HEAD` ile doğrulanacak; force push yok.

## EKSİKLER

1. **LTX-2/ComfyUI üretimi yok**: yerel GPU ve model dosyası yok; ücretli GPU onayı gerekir.
2. Video stilize vektörel animasyon; sinematik/profesyonel kalite değil. Diyalog yok,
   tek anlatıcı sesi var; karakter seslendirmesi yok.
3. İşçi katkısı rol ataması düzeyinde; 47 kanıtsız işçi için gerçek görev partisi yok.
4. Alman seslendirme tek anlatıcı; dudak senkronu yok (animasyon stili gereği yüz animasyonu sınırlı).
5. Sahip parolası hâlâ Harun tarafından belirlenmedi.
