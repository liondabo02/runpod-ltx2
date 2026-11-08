# S01E001 — İlk sahne, 2D iskelet teknik testi

**Durum:** `TECHNICAL_TEST_PENDING_REVIEW` · **profesyonel kalite: HAYIR** · **3D değil** · sessiz

- Video: `S01E001-SCENE01-2D-RIG-1080p24.mp4`
- 1920×1080 · 24 fps · 240 kare · 10,0 sn · H.264 · 476.537 bayt
- SHA-256: `d8731bbf…380e24`
- Yöntem: **PIL ile 2D vector puppet** — kalça/diz/ayak, omuz/dirsek/el, boyun/baş, gözler ve ağız ayrı; FFmpeg encode.
- Sahne: Aden yürür (0–4), durur ve el sallar (4–6), konuşma ağzı (6–9); Kaan emekler ve bakar (0–4), gülümser; ikisi etkileşir.

## Dürüst sınırlar

- **3D mesh/rig yok.** Çıktı 2D iskelet testidir; "3D" olarak etiketlenmedi.
- Yüz, kabul edilen posterin **vektör yaklaşımı**; birebir kimlik onayı yok.
- **Ses yok**, dudak senkronu gerçek fonemlere bağlı değil; ağız hareketi zamanlamaya bağlı.
- Profesyonel üretim kapısı: **FAIL** (model sheet/rig/voice/lipsync kanıtı yok).
- Storyboard kapısı: PASS; kimlik kilidi: PASS.
- Lisans: **UNVERIFIED**.

## Kanıt

- `qa.json` — ffprobe, kare farkı, boş kare sayısı
- `evidence/frame-0000.png`, `frame-0120.png`, `frame-0239.png`
- `studio_production_gate.py --level storyboard` → exit 0
- `studio_production_gate.py --level professional` → exit 2
