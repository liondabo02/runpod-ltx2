# Cartoon Factory

Otonom, tekrar eden 10 karakterli 2D çizgi film üretim katmanı.

## Hedef

Tek doğal dil komutundan:

1. senaryo ve diyalog
2. sahne manifesti
3. sabit karakter/asset kullanımı
4. TTS + lip-sync
5. müzik/SFX planı
6. 2D sprite compositing
7. final MP4

üretmek.

## Tek komut

```bash
cd cartoon_factory
python run_pipeline.py "Aras ve Robo paylaşmayı öğreniyor. 5-8 yaş, komik ve eğitici." --episode-id episode_001
```

Final dosya:

```text
cartoon_factory/output/episode_001/episode_001.mp4
```

## Gerekli bileşenler

- Python 3.11+
- FFmpeg
- Piper TTS
- Rhubarb Lip Sync
- OpenAI-compatible LLM endpoint (varsayılan OpenRouter `openrouter/free`)
- Opsiyonel RunPod/LTX-2 endpoint: özel generative-video sahneleri için

## 10 karakteri kilitleme

`config/series.yaml` kişilik, rol ve hikâye kurallarını tutar.
`config/assets.yaml` her karakter için zorunlu görsel ve ses asset sözleşmesini tanımlar.

Her karakter için minimum:

```text
assets/characters/<id>/
  poses/
    idle_front.png
    talk_front.png
    walk_front.png
    run_front.png
    sit_front.png
    jump_front.png
    point_front.png
    wave_front.png
  faces/
    neutral.png
    happy.png
    sad.png
    angry.png
    surprised.png
    scared.png
    thinking.png
    laughing.png
  mouths/
    X.png A.png B.png C.png D.png E.png F.png G.png
```

Ses modelleri:

```text
assets/voices/<character_id>.onnx
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

## Arka planlar

Sistem önce şu yolu arar:

```text
assets/backgrounds/<location>.png
```

Bulamazsa geçici düz renk arka plan üretir. İleride ComfyUI arka-plan worker'ı bu assetleri otomatik dolduracak.

## GPU özel sahneler

Senaryo motoru normal sahneleri `sprite`, gerçekten generative-video gerektiren sahneleri `gpu_special` olarak işaretler. Böylece tüm 8 dakikayı pahalı video modelinden üretmek yerine yalnız gerekli sahneler mevcut RunPod/LTX-2 altyapısına gönderilebilir.

## Önemli mevcut durum

Kod zinciri kurulmuştur; gerçek seri kalitesi için 10 nihai karakterin PNG/rig assetleri ve 10 sabit ses modeli eklenmelidir. Asset yoksa renderer yalnız mevcut arka plan/fallback sahnesini üretir. Bu bilinçli bir fail-soft davranıştır.
