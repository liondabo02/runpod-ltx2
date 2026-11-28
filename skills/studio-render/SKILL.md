---
name: studio-render
description: Blender (workbench/eevee) ile plan başına render ve ses birleştirme; maliyet-süre denetimi
when_to_use: Sahne ve animasyon hazır olduğunda plan plan render alırken.
---

# studio-render

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- scene.blend
- shot_plan.json
- wav

## Prosedür
1. Önce düşük çözünürlüklü önizleme; sorun yoksa tam render.
2. Sınırlı animasyon stili (12 fps) planlanmışsa kareyi çoğaltarak 24 fps'e taşı.
3. Her plan mp4 (video+ses) olarak yazılır; ffprobe ile akışları doğrula.
4. Render süresi ve CPU/GPU kullanımını bütçe kaydına yaz; yarıda kalırsa kalan planlardan devam et (resume).

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- 1920x1080 24 fps
- Ses akışı var
- Donmuş kare yok
- Hash ve süre kaydı

## Yasak
- Ücretli GPU çağrısı sahip onayı olmadan
- Tüm bölümü tek seferde render etmek (resume imkânsız)
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- MEK-06 Karakter gölgesi ve ışık yönü [VAR]: `tools/puppet2d.py`
<!-- MOTORLAR:BITIS -->
