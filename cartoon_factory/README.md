# Cartoon Factory

Otonom, tekrar eden 10 karakterli 2D çizgi film üretim katmanı.

## Kalite hedefi

Amaç yalnız teknik demo üretmek değil; çocukların izleyebileceği, görsel kimliği tutarlı, tekrar eden karakterleri olan düzgün bir 2D seri üretmek. Bunun için karakter yüzü, kıyafeti, renk paleti, boy oranı, ses ve kişilik seri boyunca kilitlenir. Asset eksikse sistem fail-soft çalışır ama yayın kalitesi sayılmaz.

## Tek komut bölüm üretimi

```bash
cd cartoon_factory
python run_pipeline.py "Paylaşmayı öğrenme üzerine komik ve eğitici bir macera." --episode-id episode_001
```

Final dosya:

```text
cartoon_factory/output/episode_001/episode_001.mp4
```

## Karakter fabrikası

Önce 10 karakter için sabit model-sheet/pose seti üretilir:

```bash
python workers/generate_character_assets.py
python workers/qc_visual.py
```

`CHARACTER_COMFY_ENDPOINT` ayarlanırsa karakter üretim istekleri ComfyUI/RunPod endpointine gönderilir. Her karakter için aynı stil, yüz, saç, kıyafet ve oranları koruyan prompt sözleşmesi kullanılır.

## 10 karakteri kilitleme

`config/series.yaml` kişilik, rol, hikâye ve TV-kalitesi görsel stil kurallarını tutar.
`config/assets.yaml` her karakter için zorunlu görsel ve ses asset sözleşmesini tanımlar.

Minimum asset yapısı:

```text
assets/characters/<id>/
  poses/
    idle_front.png
    idle_three_quarter.png
    idle_side.png
    idle_back.png
    talk_front.png
    walk_front.png
    run_front.png
    sit_front.png
    jump_front.png
    point_front.png
    wave_front.png
  faces/
    neutral.png happy.png sad.png angry.png
    surprised.png scared.png thinking.png laughing.png
  mouths/
    X.png A.png B.png C.png D.png E.png F.png G.png
assets/voices/<id>.onnx
```

Bu dosyalar bir kez hazırlanır; sonraki bölümlerde karakter yeniden tasarlanmaz.

## Üretim zinciri

```text
idea
  -> orchestrator/main.py
  -> episode.json + jobs.json
  -> workers/music_sfx.py
  -> workers/run_jobs.py        # Piper + Rhubarb
  -> workers/sprite_renderer.py
  -> workers/finalize_episode.py
  -> episode_id.mp4
```

## GPU özel sahneler

Normal sahneler `sprite`; yalnız gerçekten ihtiyaç olan sinematik sahneler `gpu_special` olarak işaretlenir. Böylece tüm 8 dakikayı pahalı video modelinden üretmek yerine yalnız özel sahneler mevcut RunPod/LTX-2 hattına gönderilebilir.

## Mevcut durum

Kod zinciri, karakter asset sözleşmesi, karakter üretim worker'ı, TTS/lip-sync, müzik/SFX planı, sprite compositing, final montaj ve asset QC mevcut. Yayın kalitesine geçmek için sıradaki iş gerçek 10 karakter tasarımını ve sabit ses modellerini seçip üretmektir.
