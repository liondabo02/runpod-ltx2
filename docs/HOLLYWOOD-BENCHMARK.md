# Hollywood ölçütü — AHOS çizgi film kalite çıtası

Tarih: 2026-11-07 · Karar: **referans Hollywood / stüdyo kalitesi** (Pixar, DreamWorks,
Illumination seviyesi), "AI video" değil. Bu belge çıtayı ölçülebilir hale getirir.

## 1. Neden tek model çağrısı yetmez?

Hollywood kalitesi tek bir üretim adımı değil, **zincir**dir:

```text
karakter kilidi → story/board → look development → shot üretimi → edit → ses → renk → QA
```

LTX-2.5 tek başına "güzel kare" üretir; film kalitesi şu dört şeyden gelir:
1. **Karakter kilidi** (her karede aynı yüz, oran, kıyafet, renk),
2. **Sinematik dil** (lens, blocking, ışık yönü, kompozisyon),
3. **Animasyon ilkeleri** (ağırlık, anticipation, overlap, follow-through),
4. **Kurgu ve ses** (ritim, ambiyans, müzik, miks).

Bu yüzden hedef: model + **referans sistemi** + **çok çekim** + **kurgu** + **skorlu QA**.

## 2. Karakter kilidi (ürünün temeli)

Bir karakter "kilitli" sayılır ancak şu set tamamsa:

| Varlık | İçerik | Durum |
|---|---|---|
| Model sheet | ön / 3-4 / yan / arka, aynı ışıkta | bekliyor (kota) |
| İfade sheet | 6 duygu: nötr, mutlu, şaşkın, üzgün, korku, merak | bekliyor |
| El/ayak detay | 4 parmak + başparmak, ayakkabı profili | kanonda tanımlı |
| Ölçek çizelgesi | Aden 98 cm, Kaan 76 cm, oran 0,776 | kanonda tanımlı |
| Renk kilidi | hex palet + ΔE toleransı (≤8) | kanonda tanımlı |
| Sahne kıyafeti | kobalt tişört / mercan tişört, logo yok | kanonda tanımlı |
| Prop sheet | uçurtma panel renkleri + kuyruk | sahnede tanımlı |

**Merch/oyuncak için kritik:** model sheet + ölçek + renk kilidi olmadan lisanslı ürün
üretilemez. Bu yüzden karakter kilidi, sahne üretiminden **önce** gelir.

## 3. Sinematik dil (sahne başına)

- Lens: 35 mm eşdeğeri, çocuk göz hizası; f/2.8 bokeh.
- Blocking: çocuklar sol üçte bir, uçurtma sağ üst; gökyüzüne nefes alanı.
- Işık: sol arka üstten 5200K key, 6500K sky fill, rim light saçta.
- Renk script: sabah altını + yeşil çimen + mavi gökyüzü; kontrast orta.
- Kamera: **sabit veya çok yavaş push-in**; karakter kadrajdan çıkmaz.

## 4. Skorlu yaratıcı QA (1–5, 5 = sinema)

Her çekim için `characters/qc-rubric.json` ile puanlanır. Kabul: **ortalama ≥4,0**,
hiçbir boyut **<3**, ayrıca Harun onayı. Teknik PASS puanı etkilemez.

| Boyut | 5 (sinema) | 3 (izlenebilir) | 1 (ret) |
|---|---|---|---|
| Kimlik sürekliliği | her karede aynı yüz/oran | 1–2 karede kayma | kimlik bozuluyor |
| Hareket | ağırlık, overlap, doğal | mekanik ama okunur | süzülme/erime |
| Işık | yönlü, tutarlı, hacimli | düz ama tutarlı | yön değişiyor |
| Kompozisyon | sinematik, dengeli | merkezde, sıkıcı | kadraj kaybı |
| Bozulma | yok | küçük artefakt | el/yüz erimesi |
| Estetik | stüdyo kalitesi | kabul edilebilir | vektör/oyuncak görünüm |

## 5. Yol haritası (bu sırayla)

1. **Karakter kilidi**: 2 karakter × 4 görünüş + ifade sheet (ücretsiz HF / onaylı API).
2. **Shot 01**: aynı keyframe'den 3 çekim; rubric ile seçim; Harun onayı.
3. **3 sahnelik pilot (20–30 sn)**: story → board → 3× shot → ses (edge-tts) → kurgu
   (Remotion/ffmpeg) → bağımsız QA → teslim kaydı.
4. **Seri hattı**: bölüm başına story/board/shot/QA işçi görevleri; her katkı
   `mission_id + worker_id + dosya + QA` ile kayıtlı.
5. **Merch**: onaylı model sheet + ölçek + renk kilidi ile oyuncak/lisans paketi.

## 6. Mevcut gerçeklik (dürüst)

- take1: teknik PASS, **yaratıcı RED** (kamera çocuklardan uzaklaşıyor; Kaan'ın yaşı).
- take2 (sabit kamera): **ZeroGPU kotası** nedeniyle alınamadı.
- Ücret: 0 USD. RunPod: kimlik var, ağ yolu yok.
- Hollywood çıtasına ulaşmak için gereken: **karakter kilidi + 3 çekim + kurgu + ses**;
  bunun ilk adımı ücretsiz HF tokeni veya onaylı API.

> Kural: hiçbir çekim "dosya açılıyor" diye bu çıtayı geçmiş sayılmaz. Puan Harun'undur.
