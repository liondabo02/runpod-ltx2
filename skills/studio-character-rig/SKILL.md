---
name: studio-character-rig
description: Onaylı karakterden gerçek, katmanlı 2D/3D rig üretme ve deformation doğrulama prosedürü
when_to_use: Karakterin yüzü/kimliği korunarak yürüme, el sallama, göz kırpma, konuşma veya nesne etkileşimi gerektiğinde.
---

# Studio Character Rig

## Girdi
- `studio/reference/owner_accepted_roster_v1/characters/<id>.png` (salt okunur)
- Karakter kanonu ve `identity-lock.json`
- Hedef sahne/motion sözleşmesi

## Prosedür
1. Referansı ve kimlik kilidini doğrula; SHA değişmişse dur.
2. Katmanları ayır: baş, saç, yüz, gözler, kapaklar, kaşlar, ağız, gövde,
   üst/alt kol, el, üst/alt bacak, ayak. Eksik arka planı doldurmadan hareket ettirme.
3. Pivotları bağla: boyun, omuz, dirsek, bilek, kalça, diz, ayak bileği.
4. Yüz kontrolleri: blink.L/R, smile, mouth_open, brow_up; konuşan karakterde viseme.
5. Deformasyon testi: kol kalkınca kopma yok, ayak zeminde, yüz kaymıyor.
6. `blender -b -noaudio --factory-startup --python <build>.py -- --out <dir>`
   veya 2D katman renderer'ı çalıştır.
7. Yeniden açma doğrulaması ve SHA/manifest yaz.

## Kabul
- En az 20 eklem, 3 aksiyon, 1 blink, 1 konuşma.
- 640×640 önizleme; gerçek eklem hareketi; yetim vertex 0.
- `PENDING_IDENTITY_REVIEW`; sahip onayı olmadan `IDENTITY_APPROVED` yazılmaz.

## Yasak
- Tek PNG'yi kaydırarak yürüyüş/oyunculuk taklidi.
- Onaysız yüzü "onaylı karakter" diye sunmak.
- Kapı eşiklerini düşürmek.
