---
name: studio-editing-sound
description: Kurgu, müzik, ses tasarımı ve altyazı
when_to_use: Plan mp4'leri bölüme birleştirirken; müzik/ses efektleri eklerken.
---

# studio-editing-sound

Bu skill diziden bağımsızdır; dizi bilgisi `series/<series_id>/series-bible.json` içindedir.

## Girdi
- shot mp4'leri
- music bed
- altyazı

## Prosedür
1. Kurgu ritmi: beat_sheet tempo eğrisine uy; kesme noktaları duyguyla hizalı.
2. Müzik: tema + 2 varyasyon (sakin/heyecan); ses seviyesi normalize.
3. Ses efektleri (foley) listesi beat'ten çıkar; boş kalan yerlerde sessizlik de bir tercihtir.
4. 3 farklı kurgu ritmi önizle, bağımsız QA seçer.
5. Süre ±2 sn; altyazı senkron < 200 ms.

## Yaratıcılık protokolü (zorunlu, bkz. skills/_shared/CREATIVITY-PROTOCOL.md)
1. Brief'i oku; "güvenli ortalama" çözümü ilk fikir say, SON seçenek olarak tut.
2. En az 3 FARKLI seçenek üret (farklı niyet/duygu/biçim; renk değiştirmek farklılık sayılmaz).
3. Seçimi üretici yapmaz: bağımsız QA/Eleştirmen rubrikle seçer, gerekçeyi `decision_log` a yazar.
4. Orijinallik: bilinen bir karakteri, eseri, logoyu veya sesi kopyalama.
5. Reddedilen her iş bir ders satırı olarak `studio/agents/memory/<worker_id>.jsonl` a yazılır.

## Kabul
- Süre hedefte
- Loudness normalize
- Altyazı doğru
- Müzik lisansı kayıtlı

## Yasak
- Lisanssız müzik veya ses
- Klip tekrarıyla süre doldurmak
- Kendi işini kendi onaylamak (bağımsız QA zorunlu).

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- SES-03 Ses temizleme: sessizlik kırpma, seviye eşitleme [VAR]: `tools/audio_polish.py`
- SES-04 Foley (adım, kapı, kumaş) olaydan türetilir [KISMI]: `tools/sfx_events.py` — açık: C3f
- SES-05 Ortam sesi (mekâna göre ambiyans katmanı) [YOK]: araç yok
- SES-06 Diyalogda müziğin kısılması (ducking) ve ölçüsü [VAR]: `tools/audio_qa.py`
- MUZ-01 Dizinin ana teması her bölümde geri gelir [VAR, insan onayı]: `tools/score_engine.py`
- MUZ-02 Sahne yoğunluğuna göre müzik [VAR, insan onayı]: `tools/score_engine.py`
- MUZ-03 Sahne geçişinde müzik vurgusu [TESTSIZ]: `tools/score_engine.py`
- EFX-01 Duygu simgeleri (kalp, yıldız, ter) [VAR]: `tools/fx_layer.py`
- EFX-02 Sahne geçişleri (iris, silme) [VAR]: `tools/fx_layer.py`
- EFX-03 Hız çizgileri ve darbe efektleri [YOK]: araç yok
- EFX-04 Basışa bağlı yürüme tozu [VAR]: `tools/fx_layer.py`
<!-- MOTORLAR:BITIS -->
