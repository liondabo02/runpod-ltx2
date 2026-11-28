---
name: studio-animation-acting
description: Duygu verisiyle (valence/arousal/intensity) oyunculuk animasyonu
when_to_use: beat_sheet ve rig hazır olduğunda her vuruşu hareketlendirirken.
---

# studio-animation-acting

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- rig-contract.json
- beat_sheet.json
- emotion_curve

## Prosedür
1. Her vuruş için 'niyet → jest' belirle: karakter ne istiyor, bunu bedeniyle nasıl gösterir.
2. Duygu → hareket eşlemesi: arousal tempo/jest boyutu, valence duruş/kaş, intensity genlik.
3. Anticipation, follow-through, squash/stretch ve 'tutuş' (hold) kullan; mekanik kaydırma yok.
4. Her vuruş için 3 farklı oyunculuk seçeneği küçük önizlemeyle; bağımsız QA seçer.
5. Bake et; ayak kayması ve ani sıçrama testini çalıştır.

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Tüm vuruşlar mevcut
- Ayaklar zeminde, ayak kayması < 5 mm
- Kare başına açı sıçraması < 15°
- Aynı jest art arda tekrar etmiyor

## Yasak
- Tek PNG kaydırarak animasyon
- Aynı döngüyü her sahnede tekrar kullanmak
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- ANI-01 Yürüyüşte basılı ayak, ayak kayması ölçü ve kapısı [KISMI]: `tools/foot_slide.py`, `tools/readability.py` — açık: H6b, H27, H28
- ANI-02 Poz geçişi sıçramasız (poz sıçraması kapısı) [KISMI]: `tools/pose_blend.py`, `tools/readability.py` — açık: C2a
- ANI-03 Ezme-esneme (squash & stretch) [TESTSIZ]: `tools/puppet2d.py`
- ANI-04 Hazırlık (anticipation) ve toparlanma ölçüsü [VAR]: `tools/motion_continuity.py`
- ANI-05 Takip ve bindirme (saç, kulak, giysi gecikmesi) [YOK]: araç yok
- ANI-06 İkincil hareket (ana eylemi destekleyen küçük hareketler) [YOK]: araç yok
- ANI-07 Hareketli tutuş (beklerken nefes/salınım) [TESTSIZ]: `tools/shot_motion.py`
- ANI-08 Göz kırpma (şaşırmada kırpmama dahil) [VAR]: `tools/render2d.py`
- ANI-09 Bakış: eylemi izleme, önce bak sonra konuş [KISMI]: `tools/listener_reaction.py` — açık: H14
- ANI-10 Dinleyen karakterin tepkisi [VAR, insan onayı]: `tools/listener_reaction.py`
- ANI-11 Önden/üç-çeyrekten profile yumuşak dönüş [KISMI]: `tools/puppet_side.py` — açık: C2a, H23, H18
- ANI-12 Duygu ifadesi (kaş, ağız, göz) [KISMI, insan onayı]: `tools/puppet2d.py` — açık: H24
- ANI-13 Nesne tutma, devir, atış, bırakma [KISMI]: `tools/continuity.py`, `tools/readability.py` — açık: C3a, C3b, C3c, C3d, C3e, C3f, C3g, C3h
<!-- MOTORLAR:BITIS -->
