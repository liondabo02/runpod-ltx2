# S04–S05 kuyruk sürekliliği düzeltmesi

Tarih: 2026-11-08 · Durum: **taslak, onay yok** · v1 ve POC değiştirilmedi

## Sorun

v2'de S04'te kuyruk **bütün hâlde** piknik örtüsüne düşüyor, S05'te ise çok sayıda
parça aranıyordu. Seyirci için "tek kuyruk nasıl altı parçaya ayrıldı?" sorusu
yanıtsız kalıyordu.

## Çözüm (tek kurgu)

Kuyruk **altı büyük kumaş şeritten** oluşur; şeritler düğümlerle birbirine bağlıdır.

| Şerit | Nereye düştü |
|---|---|
| kırmızı | piknik örtüsü |
| sarı | piknik örtüsü |
| mavi | piknik örtüsü |
| yeşil | papatya yanındaki çimen |
| turuncu | papatya yanındaki çimen |
| mor | alçak çalı |

**S04:** Rüzgâr düğümleri sırayla açar; şeritler havada tek tek ayrılır ve yukarıdaki
noktalara düşer. **S05:** Aynı altı şerit aynı yerlerden toplanır (üçü örtüden,
ikisi çimenden, biri çalıdan — sonuncusunu Esra alır). "Eksik parça" repliği kaldırıldı.

**S07:** İlk onarımda yalnız üç şerit (kırmızı/sarı/mavi) kullanılır → kuyruk kısa kalır.
**S08:** Kalan üç şerit (yeşil/turuncu/mor) eklenir → altı şeritli kuyruk tamamlanır.

## Doğrulama

- `tools/validate_s01e001_v2.py`: PASS (480 sn, 30 sn açılış, kronoloji).
- Yeni test: `ahos_core/tests/test_s01e001_tail_continuity.py`
  - altı şerit, benzersiz renkler, 3+2+1 iniş dağılımı
  - S04'te altı rengin ayrılması, S05'te aynı altı rengin bulunması
  - "eksik" ifadesinin olmaması
  - S07 üç / S08 kalan üç onarım sırası
- Mevcut v1 testleri (6) ve v2 testleri (8) korunur.

## Sınırlar

- Bu bir **senaryo düzeltmesidir**; görsel üretim yok.
- v1 ve bağımsız POC dosyalarına dokunulmadı.
- Sahip onayı olmadan final değil.
