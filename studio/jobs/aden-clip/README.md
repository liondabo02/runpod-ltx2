# Aden — 5 saniyelik yerel klip

- Video: `aden_idle_5s.mp4` — 768×512, 24 fps, 5.000 sn, 120 kare
- Sesli sürüm: `aden_idle_5s_voiced.mp4` — aynı video + geçici Türkçe ses + Rhubarb viseme
- Üretim: Blender 4.5.16 Workbench, Aden rig (`idle_wave` döngüsü)
- Ses: edge-tts geçici yetişkin ses; **final karakter sesi değil**
- Kimlik: **PENDING_IDENTITY_REVIEW** (onaylı final değil)
- QA: `qa.json` ve `qa_voiced.json` — tüm kontroller PASS
- Önizleme: `preview.png` / `preview_voiced.png`

## Yeniden üretim

```powershell
blender -b studio\jobs\aden-rig\rig\aden\aden-rigged.blend -noaudio --factory-startup \
  --python tools\render_aden_clip.py -- --out studio\jobs\aden-clip\frames
ffmpeg -y -framerate 24 -i studio\jobs\aden-clip\frames\f%04d.png \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart \
  studio\jobs\aden-clip\aden_idle_5s.mp4
python tools\qa_local_clip.py
```

Bu klip **LTX değildir**; GPU/Colab olmadan gerçek, hareketli bir teslim üretmek için
yerel Blender yoludur. LTX/Colab çıktısı geldiğinde ayrıca değerlendirilir.
