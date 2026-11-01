# Çizgi film stüdyosu — kullanım ve kabul kuralları

Tek komutla bölüm üretir; üretim sonucu **bağımsız kapıdan** geçmeden teslim sayılmaz.

## Üretim

```bash
# sahip komutu (niyet algılanır)
python -m ahos.owner_cli --runtime-dir ./runtime --scenes 3 --seconds 3 "çizgi film: parkta bir gün"

# doğrudan hat
python -m ahos.studio_pipeline --out ./bolum --scenes 12 --seconds 5 "parkta bir gün"

# sessiz (seslendirme olmadan)
python -m ahos.owner_cli "çizgi film: test" --no-voice
```

Kurulu konsol betiği: `ahos-studio` (pyproject `[project.scripts]`).

## Üretilenler

| Dosya | İçerik |
|---|---|
| `episode.mp4` | H.264 + AAC, 1280×720, 24 fps |
| `episode.srt` | Replik altyazıları |
| `timeline.json` | Replik başlangıç/bitiş, konuşmacı, metin |
| `story.json` / `brief.json` | Senaryo ve künye |
| `voice/line_XX.wav` | Replik başına ses |
| `acceptance.json` | Kapı ölçümleri ve kararı |

## Kabul kuralları (hepsi dosyadan ölçülür)

1. **Oynatılabilirlik**: ffprobe video akışı, süre > 0,5 sn, ≥ 640×360.
2. **Süre**: beyan edilen süre ile gerçek süre arasında ±%5.
3. **Hareket**: 4 fps örneklemede ≥0,75 sn boyunca değişen piksel oranı
   %0,2'nin altındaysa "donmuş" → **ret** (slayt teslimi kabul edilmez).
4. **Sahne**: senaryonun görsel planındaki kesme sayısı (`expected_cuts`).
5. **Ses**: beyan varsa akış zorunlu; RMS < 120 ise "sessiz" → ret;
   ses/video süresi 0,75 sn'den fazla kayarsa ret.
6. **Altyazı**: `.srt` var ve satır sayısı > 0.

Skor: her problem −25, ses yoksa −10; ≥70 ve problem yoksa geçer.

## Seslendirme

Motor sırası: `edge` → `piper` → `sapi`.

| Motor | Dil | Not |
|---|---|---|
| `edge` (edge-tts) | tr, en, de | Ücretsiz, anahtarsız; karakter başına ses (Aden=Emel, Kaan=Ahmet) |
| `piper` | model neyse | `AHOS_PIPER_VOICE` ile `.onnx` yolu |
| `sapi` | kurulu sesler | Çevrimdışı; makinede tr yoksa aksan bozuk, `language_match=false` |

Zorlamak için: `AHOS_VOICE_ENGINE=edge|piper|sapi`.

## Ölçülen referans koşu

| Bölüm | Süre | Kapı | Ses | Render |
|---|---|---|---|---|
| 3 sahne pilot | 18 sn | 100 | de-DE | ~25 sn |
| tam bölüm (Türkçe) | 480 sn | 100 | tr-TR, 2 rol | 566 sn |

Uzun bölümlerde kareler diske yazılmaz, doğrudan ffmpeg'e akıtılır
(`image2pipe`); 1500 kareden kısa bölümlerde kareler hata ayıklama için kalır.

## Sınırlar

- Görsel stil kodla çizilen 2D'dir; sinematik AI video katmanı RunPod
  anahtarına bağlıdır (`AHOS_RUNPOD_ENABLED`, `RUNPOD_API_KEY`).
- Kapı teknik ve yapısal kaliteyi doğrular; sanatsal kaliteyi doğrulamaz
  (`acceptance.json` içindeki `scope` alanı bunu açıkça yazar).
