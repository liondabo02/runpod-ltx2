# Üretim ortamı (tek, belgelenmiş)

Tarih: 2026-11-07 · Kanonik ortam: **`control_plane_v2/.venv`** (Python 3.12.7)

Genel Python (`C:\Users\esmak\AppData\Local\Programs\Python\Python312`) da çalışır
ama **tekrarlanabilir üretim ortamı venv'tir**. Testler bu ortamda koşulur.

## Kurulum

```powershell
cd C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
control_plane_v2\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Doğrulanan sürümler (venv)

| Paket | Sürüm |
|---|---|
| Python | 3.12.7 |
| opencv (headless) | 5.0.0 |
| gradio_client | 2.7.2 |
| huggingface_hub | 1.31.0 |
| transformers | 5.20.2 |

## Test komutu (kanonik)

```powershell
cd ahos_core
..\control_plane_v2\.venv\Scripts\python.exe -B -m pytest -q --no-header -p no:cacheprovider `
  tests/test_character_canon.py tests/test_audio_audit.py `
  tests/test_scene_tools.py tests/test_creative_qa.py
```

Beklenen: **14 passed**, exit 0. Aynı set genel Python'da da geçer; fark yalnız
ortam bağımlılıklarıdır (`cv2`, `gradio_client`) ve venv'e kurulmuştur.

## Neden venv?

- `creative_qa` kare ölçümü için `cv2` ister.
- `ltx_space_render` Hugging Face Space çağrıları için `gradio_client` ister.
- Venv, control plane servislerinin kullandığı ortamdır; test ile üretim aynı
  bağımlılık setini paylaşır.

## Ortam kontrolü

```powershell
control_plane_v2\.venv\Scripts\python.exe -c "import cv2, gradio_client, huggingface_hub, transformers; print('ok')"
```
