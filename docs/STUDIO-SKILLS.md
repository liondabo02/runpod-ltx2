# AHOS Studio Professional Skills

Bu katalog, stüdyonun **profesyonel üretim prosedürlerini** ajanların okuyabileceği
`SKILL.md` dosyaları olarak taşır. Skill bir model veya motor değildir; rig, ses,
video, QA ve uzun bölüm işlerinde **nasıl doğrulama yapılacağını** tanımlar.

## Katalog

| Skill | Kullanım |
|---|---|
| `studio-character-rig` | Katmanlı karakter rig'i, deformation, blink/walk |
| `studio-voice-lipsync` | Kalıcı ses kimliği, WAV, fonem/viseme |
| `studio-cinematic-video` | Referans kontrollü video, GPU/ücret kapıları |
| `studio-longform-production` | Çok sahneli bölüm, job ledger/resume |
| `studio-media-qa` | Fail-closed video/ses/kimlik/lisans denetimi |
| `studio-provider-integration` | Model-agnostik sağlayıcı/adapter sözleşmesi |

## Kullanım

```bash
cd ahos_core
python -m ahos.studio_skills --list
python -m ahos.studio_skills --search lip-sync
python -m ahos.studio_skills --show studio-character-rig
```

Kurulu komut: `ahos-skills`.

Ajanlara verilecek ilk talimat:

```text
Göreve başlamadan önce ilgili SKILL.md dosyasını oku.
Kabul kriterlerini ve yasakları uygula; kanıt olmadan "tamam" deme.
```

## Dürüst sınır

Bu dosyalar **yetenek değil, prosedürdür**. Örneğin `studio-character-rig` tek başına
3B model üretmez; Blender/rig aracı, onaylı referans ve gerçek çıktı gerekir.
GPU yoksa `studio-cinematic-video` motoru çalışmaz; skill bunu gizlemez.
