# AHOS-DELIVERY-001 — Üretim Ortamı Durumu (Faz 1)

- Üretim: 2026-11-07T09:48:07
- GPU: **yok**
- ffmpeg: `C:\Users\esmak\AppData\Local\Programs\Python\Python312\Scripts\ffmpeg.EXE` · ffprobe: `C:\Users\esmak\AppData\Local\Programs\Python\Python312\Scripts\ffprobe.EXE`
- edge-tts: **True**
- Model dosyası (safetensors): **0**
- RunPod/Comfy env anahtarları: AHOS_RUNPOD_ENABLED, AHOS_RUNPOD_ENDPOINT, AHOS_RUNPOD_ENDPOINT_IMAGE, AHOS_RUNPOD_ENDPOINT_TTS, AHOS_RUNPOD_ENDPOINT_VIDEO, RUNPOD_API_KEY
- Engellenmiş üretim görevi: **0**

## Karar

Yerel GPU yok; LTX-2/ComfyUI model üretimi ücretli GPU/API olmadan çalıştırılamaz. Deterministik PIL+ffmpeg+edge-tts hattı çalışıyor. Ücretli kaynak için Harun onayı gerekir.

## Engellenmiş görevler

- yok

## Ücret

- Bu tanı 0 $; hiçbir ücretli API/GPU çağrısı yapılmadı.
