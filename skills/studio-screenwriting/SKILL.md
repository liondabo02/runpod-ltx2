---
name: studio-screenwriting
description: Diziden bağımsız, yaş bandına uygun 8+ dakikalık bölüm senaryosu; Yazar → Eleştirmen → Düzeltmen döngüsü ve saniye saniye eylem çizelgesi
when_to_use: Sahibi yeni bir hikâye fikri, karakter tarifi veya bölüm istediğinde; senaryo/shot-list yazılırken veya revize edilirken.
---

# Studio Screenwriting (Yazarlar Odası)

Bu skill belirli bir diziye bağlı DEĞİL. Dizi bilgisi her zaman `series/<series_id>/series-bible.json` dosyasından okunur.

## Girdi
- Sahibin kısa fikri (1–10 cümle), dil (TR/DE...), yaş bandı, hedef süre (varsayılan 480 sn, minimum).
- `series/<series_id>/series-bible.json` (karakterler, mekânlar, ses kimlikleri, önceki bölüm özeti).

## Üç rol, üç ayrı çağrı (kendini onaylama YOK)
1. **Yazar:** fikirden `beat_sheet.json` üretir.
2. **Eleştirmen:** Yazarın çıktısını görmeden değil, YALNIZ çıktı + rubrik ile puanlar. Mümkünse Yazardan farklı bir model kullanılır (OmniRoute `auto` farklı sağlayıcı seçebilir).
3. **Düzeltmen:** Eleştirmenin maddelerini düzeltir. En fazla 2 düzeltme turu; sonra insana "NEEDS_REVIEW" gider.

## Çıktı: `beat_sheet.json`
Her vuruş (beat) 5–10 saniye. Alanlar:
`t_start`, `t_end`, `scene_id`, `location`, `light_time`, `characters`, `action` (kamerada GÖRÜNEN somut eylem), `dialogue` (boş olabilir), `emotion` (valence/arousal/intensity), `camera`, `sound`, `safety_note`.

## Zorunlu yapı (480 sn)
- 0–15 sn: görsel merak kancası (diyalogsuz olabilir).
- 15–60 sn: somut hedef + ilk engel.
- Orta: en az 3 "dene–başarısız ol–değiştir" döngüsü, her biri duygu değişimiyle.
- Son 60 sn: çözüm + sıcak kapanış; dersi karakter DAVRANIŞIYLA göster, sloganla söyleme.
- Diyalog az olabilir; boşluğu sabit kadrajla DOLDURMA: eylem, sessiz görsel espri, müzik, mikro-vuruş yaz.
- Mekân ve ışık mantığı tutarlı: her mekân değişiminde geçiş vuruşu veya tek mekân.

## Rubrik (Eleştirmen, 100 puan)
Merak/akış 20 · Yaşa uygun hareket ve replik 20 · Karakter kimliği/süreklilik 20 · Eylem çeşitliliği 15 · Doğal ses ve duygu 15 · Güvenlik 10.
Her puan için bir beat numarası kanıt olarak yazılır. Kanıtsız puan geçersiz. Geçme eşiği: ≥ 80 ve Güvenlik 10/10.

## Güvenlik kuralları (0–3 yaş karakter dahil)
- Yetişkin kontrolü olmadan ip, kordon, küçük parça, kumaş şeridi bebeğe verilmez.
- Boğulma/dolanma riski taşıyan eylem yok.
- Bebek karakter için 2–4 kısa ses/kelime; uzun cümle yok.
- Karakterin ilişkisi kanonda yoksa uydurulmaz.

## Yasak
- Tek karakterin kimliğini veya yüzünü senaryoda değiştirmek.
- Bölüm süresini sahte uzatmak (aynı kareyi bekletmek).
- Yaratıcı onayı kendi vermek: onay yalnız sahibindedir.

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- SEN-01 Sahip senaryosundan sadık vuruşlar (replik/süre/karakter değişmez) [TESTSIZ]: `tools/script_to_beats.py`
- SEN-02 Senaryoyu bozmadan zenginleştirme (tepki/şaka/arka plan), onaya sunulur [VAR, insan onayı]: `tools/script_enrich.py`
- SEN-03 Dizi hafızası ve kanon kilidi (bölümler arası tutarlılık) [VAR]: `tools/series_memory.py`
- SEN-04 Yaz-eleştir-düzelt döngüsü [VAR]: `tools/writers_room.py`
- SEN-05 Konu -> senaryo -> sahne -> üretim -> QA izlenebilirliği [KISMI]: `tools/action_trace.py` — açık: P1, P1a
- SEN-06 Ayrı senaryo kalite değerlendirmesi (rubrik; üretenden bağımsız) [YOK]: araç yok — açık: P1
- SEN-07 Çocuk programı yazım kalıpları ölçüsü (tekrar, çağrı-cevap, ödül anı) [YOK]: araç yok
<!-- MOTORLAR:BITIS -->
