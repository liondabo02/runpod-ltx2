# Aden & Kaan — karakter kanonu ve referans sistemi

Tarih: 2026-11-07 · Sürüm: `v1` · Kaynak: mevcut tasarım kararları
(`ahos_core/ahos/studio_2d.py` paleti) + yaş bilgisi (Aden 3, Kaan 1).

Makine-okunur kanon: `characters/aden.json`, `characters/kaan.json`,
sahne: `characters/scenes/park-kite-01.json`.

## 1. Kanon neden gerekli?

Video modelleri her çekimde yüzü, saçı ve kıyafeti kaydırır. Süreklilik, modelin
"iyi niyetine" bırakılmaz; **ölçülebilir referans** ile zorlanır:

1. Sabit palet (hex) ve oran (boy, kafa/gövde).
2. Her karakter için 3 görünüşlü referans sayfası (ön / 3-4 yan / arka).
3. Sahne keyframe'i (ilk kare) + I2V.
4. Sabit seed ve aynı prompt fragmanı.
5. Teslimde otomatik süreklilik ölçümü (renk, oran) + insan gözü.

## 2. Aden (3 yaş, kız, 98 cm)

| Alan | Değer |
|---|---|
| Cinsiyet | **kız** (eski ses kataloğu ve production plan ile aynı) |
| Ten | `#F5CDAA` (gölge `#E3AE86`), yanak `#EFA98E` |
| Saç | `#462D1E`, omuz hizasında dalgalı, yandan ayrık, yumuşak perçem, **sarı yıldız toka** |
| Göz | `#3A2A1E`, büyük, koyu ela, catchlight |
| Üst | Kobalt mavi tişört `#286EC8`, küçük sarı uçurtma baskısı |
| Alt | Lacivert şort `#283246` |
| Ayakkabı | Krem `#F7F4EC`, mavi taban `#286EC8` |
| Oran | 3,6 kafa boyu; yuvarlak yanak, düğme burun |
| İmza | Sol yanağın üstünde **3 çil** |

## 3. Kaan (1 yaş, 76 cm)

| Alan | Değer |
|---|---|
| Ten | `#E8BE96` (gölge `#D3A277`), yanak `#E39A80` |
| Saç | `#19191E`, kısa yumuşak kıvırcık, alında bukle |
| Göz | `#241A14`, çok büyük, koyu |
| Üst | Mercan kırmızısı tişört `#DC5A46` |
| Alt | Lacivert yumuşak şort `#3C3C5A` |
| Ayakkabı | Krem bebek ayakkabısı `#F3E7D3` |
| Oran | 3,1 kafa boyu; tombul yanak, iki dişli gülümseme |
| İmza | Sağ kulak arkasında küçük kıvırcık tutam |

**Boy oranı:** Kaan / Aden = 76/98 = **0,776**. Sahnede ±%5 dışına çıkarsa ret.

## 4. Sahne kanonu (S01-PARK-KITE-001)

- 6 sn, 1920×1080, 24 fps, 16:9.
- Yemyeşil park, bahar sabahı, 2–3 m/s esinti, alçak açı (çocuk göz hizası 0,95 m).
- Kompozisyon: çocuklar **sol üçte bir**, uçurtma **sağ üst**, gökyüzüne nefes alanı.
- Işık: sol arka üstten 5200K güneş + 6500K gökyüzü dolgusu, yumuşak gölge.
- Uçurtma: elmas, panel renkleri `#FFD65A` `#E64860` `#4084DC` `#6EBE78`, uzun gökkuşağı kuyruk.
- Hareket: 0–1,2 sn hazırlık; 1,2–3,0 sn rüzgâr + sevinç; 3,0–4,8 sn uçurtma yükselir,
  kamera hafif yükselir; 4,8–6,0 sn sıcak kapanış.

## 5. Referans üretim planı (henüz üretilemedi)

| Adım | Araç | Durum |
|---|---|---|
| Aden 3 görünüş sayfası | Flux Pro / Nano Banana / LTX-2.5 image | **ücretsiz kademe kapalı (HTTP 402)**, anahtar gerekli |
| Kaan 3 görünüş sayfası | aynı | aynı |
| Sahne keyframe (1920×1080) | aynı + sahne promptu | aynı |
| I2V | LTX-2.5 Pro I2V | anahtar gerekli |

Prompt fragmanları kanon JSON'larında hazır: `prompt_fragment` ve `negative_fragment`.
Görsel model çağrısı şu şablonla yapılır:

```text
<character.prompt_fragment> + "three-view turnaround, front / three-quarter / back,
identical colors and proportions, neutral seamless background, no text" + <negative_fragment>
```

Onaylanan referans görselleri `assets/reference/<karakter>/seed-<N>.png` altında
tutulur; **git'e girmez** (manifest girer).

## 6. Ölçülebilir süreklilik kontrolü (teslimde)

| Kontrol | Yöntem | Eşik |
|---|---|---|
| Kıyafet rengi | gövde bölgesinden ortalama renk, ΔE (CIE76) | ≤ 8 |
| Saç rengi | kafa üstü bölgesi | ≤ 10 |
| Boy oranı | kare içinde karakter yükseklikleri oranı | 0,776 ± %5 |
| Yüz kimliği | referans sayfası ile CLIP-benzeri gömme kosinüsü | ≥ 0,80 (deneysel) |
| Uçurtma paneli | 4 renk kümesi eşleşmesi | 4/4 |
| Hareket | `tools/creative_qa.py` motion / freeze | freeze ≤ %30 |

Eşikler **deneysel**: ilk gerçek üretimde kalibre edilecek; şimdiden "geçer" denemez.

## 6b. Hollywood kilidi ve merch hazırlığı

Kalite çıtası: **Pixar/DreamWorks sınıfı sinema** (`docs/HOLLYWOOD-BENCHMARK.md`).
Skor: `characters/qc-rubric.json` (6 boyut, 1–5); kabul ortalaması ≥4,0 ve hiçbir boyut <3.

Bir karakter "kilitli" sayılmadan sahne üretilmez:

1. Model sheet: ön / 3-4 / yan / arka, aynı ışık ve ölçekte.
2. İfade sheet: nötr, mutlu, şaşkın, üzgün, korku, merak.
3. Ölçek çizelgesi: Aden 98 cm, Kaan 76 cm, oran 0,776.
4. Renk kilidi: hex palet + ΔE ≤ 8.
5. Prop sheet: uçurtma panelleri + kuyruk; park paleti.

**Oyuncak/lisans için:** model sheet + ölçek + renk kilidi olmadan merch üretimi
başlatılmaz. Karakter kimliği her bölümde bu dosyalarla doğrulanır.

Üretim zinciri (tutarlılık için): kanon → referans görseli → sahne keyframe'i
(referans koşullu) → I2V → renk eşleme → skorlu QA. Aynı keyframe + sabit seed
kullanılmadan çok sahneli tutarlılık beklenmez.

## 7. Sınırlar (iddia edilmeyen)

- Referans görselleri henüz **tam set değil** (take1 keyframe'i var; turnaround/ifade yok).
- Kanon, modelin sanat yönetmeni değildir; yalnız tutarlılık sözleşmesidir.
- Yüz benzerliği otomatik ölçümü insan onayının yerine geçmez.
