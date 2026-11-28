---
name: studio-character-design
description: Diziden bağımsız karakter tasarımı ve model üretimi; kimlik kilidi (hash)
when_to_use: Yeni veya konuk karakter gerektiğinde; karakter tarifinden model sheet ve 3D model üretimi.
---

# studio-character-design

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- series-bible.json ve sahibin karakter tarifi
- Referans görseller (varsa, salt okunur)

## Prosedür
1. Tarifi siluet, oran, renk paleti, yüz dili ve kişilik jestleriyle yaz (karakter sheet).
2. 3 farklı tasarım yönü üret; siluet testi: gölge halinde ayırt edilebilir olmalı.
3. Seçilen yönü Blender mesh_factory ile modelle; rig parça adlarını standartla.
4. Model, referans ve parametreler SHA ile `identity_lock`a yazılır; bible güncellenir.

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Siluet testi geçti
- Rig parça adları standart
- Vertex bütçesi aşılmadı
- Kimlik hash'i kayıtlı
- Sahip kimlik onayı: PENDING

## Yasak
- Aynı karakteri her sahnede yeniden çizmek
- Onaysız yüzü 'onaylı' saymak
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- KAR-01 Karakter yüzleri birbirinden ayrışır (özellik mesafesi ölçüsü) [KISMI]: `tools/studio_standards_check.py` — açık: Q3
- KAR-02 Yaş/boy oranlı tasarım tek kaynaktan [VAR]: `tools/puppet2d.py`
- KAR-03 Siluet testi (gölge halinde bile tanınma) [YOK]: araç yok
- KAR-05 Yüz okunurluğu (ten, gözlük, yaş) ölçü ve kapısı [VAR, insan onayı]: `tools/face_visibility.py`
<!-- MOTORLAR:BITIS -->
