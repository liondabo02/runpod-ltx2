# Cinecode ↔ AHOS entegrasyonu (P11)

Cinecode, Claude Code için kod tabanlı film üretim kitidir: HTML/Three.js sahne,
Chrome capture, ses miksajı, MP4 ve QC araçları içerir.

## Doğrulanan

- Kurulum: `C:\Users\esmak\.claude\skills\cinecode`
- `scripts/make.py`, `qc.py`, `capture.mjs`, `tts.py`, `mix.py` mevcut.
- **Bağımsız QC çalışıyor** (Claude hesabı gerekmedi):
  `tools/cinecode_adapter.py --video <mp4>` → `qc-report.json`, exit 0.
- QC: info/black/freeze/dup → tümü exit 0; video 12 sn, 288 kare, 1080p24, sessiz.

## Kullanılmayan / engelli

- `make.py` bir **film projesi + STATE.md + sahne HTML'i** ister; AHOS karakter rig'i
  olmadığı için bu proje üretilmedi.
- `tts.py` motorları: Gemini (API anahtarı), ElevenLabs (ücretli), EMA (Apache 2.0,
  ~800 MB indirme, tek yetişkin Türkçe ses). **Çocuk sesi yok**; indirme yapılmadı.
- Claude Code hesabı gerekmedi; hook güncellemesi yapılmadı.

## Kapsam

Bu katman **QC adaptörüdür**; cinecode'un sahne/render hattına karakter bağlanmadı.
Cinecode kodları değiştirilmedi.
