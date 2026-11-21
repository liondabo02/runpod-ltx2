# AHOS Studio — Demo Packet

Bu dosya, projeyi Claude’a göstermek için hazırlanmış kısa bir tanıtım ve inceleme rehberidir.

## Proje nedir?

AHOS Studio, konu metninden çizgi film bölümü üretmeyi hedefleyen yerel, ücretsiz ve doğrulanabilir bir üretim hattıdır:

```text
konu → senaryo (LLM veya deterministik şablon)
     → karakter rig'i (Blender, 24 kemik)
     → sahne render'ı (Workbench/ffmpeg)
     → Türkçe ses (edge-tts / Piper adayı)
     → Rhubarb viseme (WAV → mouthCue JSON)
     → QA (süre, çözünürlük, ses, hareket, kimlik)
```

## Kanıtlar

| Kanıt | Yol | Durum |
|---|---|---|
| Sesli 5 sn klip | `studio/jobs/aden-clip/aden_idle_5s_voiced.mp4` | 768×512 · 24 fps · 5.047 sn · AAC |
| Sessiz klip | `studio/jobs/aden-clip/aden_idle_5s.mp4` | 5.000 sn · 120 kare |
| Önizleme | `studio/jobs/aden-clip/preview_voiced.png` | 768×512 |
| QA | `studio/jobs/aden-clip/qa_voiced.json` | PASS |
| Rig | `studio/jobs/aden-rig/rig/aden/aden-rigged.blend` | 24 kemik · 5 shape key |
| Aksiyonlar | `idle_wave`, `blink_smile`, `walk_cycle` | 3 render |
| Viseme | `studio/jobs/aden-rig/lipsync/aden-line.json` | 10 mouthCue |
| Testler | `ahos_core/tests/` | 1.576+ test geçmişi; hedefli testler aşağıda |

## Hızlı çalıştırma

```powershell
cd C:\actions-runner\_work\AHOS-work-s1\ahos_core
python -m pytest tests/test_studio_2d.py tests/test_studio_voice.py tests/test_lipsync.py -q
```

Video:

```powershell
start studio\jobs\aden-clip\aden_idle_5s_voiced.mp4
```

## Dürüst sınırlar

- **LTX/Wan video yok**: GPU yok; AI video `BLOCKED_GPU`.
- **Ses geçici**: edge-tts yetişkin ses; final çocuk sesi değil.
- **Kimlik**: `PENDING_IDENTITY_REVIEW`; sahte `IDENTITY_APPROVED` yok.
- **Görsel kalite**: mevcut basit rig; Pixar seviyesi değil.
- **Colab**: LTX notebook var; çalıştırmak için Google T4 GPU hesabı gerekir.

## Claude’a inceletmek için önerilen prompt

```text
Bu repo AHOS Studio: konu → senaryo → rig → render → ses → viseme → QA hattı.
Önce PROJECT-DEMO.md, docs/CAPABILITY-MATRIX.md ve docs/INSTALL-LOG.md oku.
Sonra şu sorulara kanıtlı cevap ver:
1. Hangi parçalar gerçekten çalışıyor, hangileri iddia?
2. 5 sn klip üretim zincirindeki en zayıf halka nedir?
3. 8 dakikalık bölüme çıkmak için sıradaki 3 teknik adım ne?
4. Hangi testler/kanıtlar eksik?
Kod değiştirme; önce inceleme raporu yaz.
```

## Önemli dosyalar

- `ahos_core/ahos/studio_2d.py` — 2D çizim/punch-in/shake
- `ahos_core/ahos/studio_voice.py` — TTS, miks, SFX
- `ahos_core/ahos/lipsync.py` — Rhubarb adaptörü
- `ahos_core/ahos/series.py` — senaryo/LLM fallback
- `ahos_core/ahos/studio_pipeline.py` — üretim hattı
- `ahos_core/ahos/studio_qa.py` — kabul kapısı
- `tools/studio_backends/rig_factory.py` — Blender rig
- `tools/render_aden_voiced_clip.py` — viseme render
- `docs/INSTALL-LOG.md` — lisans/kurulum kanıtı
