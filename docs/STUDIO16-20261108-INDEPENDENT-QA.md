# AHOS Studio-16 — bağımsız teslimat/kanon denetimi (2026-11-08)

**Karar:** Hazırlık paketi SPEC_READY; üretim READY değil; hiçbir karakter APPROVED değil.

## Dayanak
- DeepSeek dalı: `feature/ahos-studio-16`, commit `e77f7ef`.
- Mevcut ana geliştirme HEAD önce `a307075`.
- `studio/canon/cast-manifest.json`: 16 benzersiz karakter.
- `studio/characters/<id>/`: 16 karakter x 6 metin/JSON dosyası.
- `studio/canon/family-relations.json`: 28 yönlü ilişki kaydı.
- `studio/production/work-orders.json`: 48 **iş emri beyanı**; bunlar otomatik yürütülen 48 görev veya 48 ürün değildir.
- `studio/s01e001/storyboard/shot-schedule.json`: 55 hareket/shot *spec* ve 480 saniye; bunlar çizilmiş storyboard kareleri veya 55 ayrı çekilmiş animasyon klibi değildir.
- Ses referansları 14/16 `READY_FOR_QA`; gerçek bölüm seslendirmeleri ve çok dilli paketler hazır değil.
- Görsel kimliği onaylı 0/16; v1 önizlemeli Aden/Kaan 2/16 NEEDS_REVISION; kalan 14 karakter için görsel kanon eksik.
- 3D model/rig/animasyon kitaplığı 0; pilot ve 8 dakikalık video oluşturulmadı.

## Bulunan ve giderilen gerçek hatalar
1. **Esma'nın başörtüsü:** Kaynak `CAST` metni açıkça "başörtülü" diyordu ama `HIJAB` kümesi Esma'yı içermiyordu. Hem üretici, hem `studio/characters/esma/character.json`, hem cast-manifest ve test düzeltildi. Başörtülü yetişkinler Esra, Esma ve Öznur.
2. **Yanlış görsel iş emri durumu:** Aden/Kaan model-sheet iş emri `READY_FOR_QA` görünüyordu, fakat bunlar onaylı v2 model-sheet dosyaları değil. İş emirleri `BLOCKED` statüsüne ve somut gerekçeye çekildi. V1 referansın bulunması nihai varlık olmadığı için ayrı tutuldu.
3. **Yeniden çalıştırmada veri kaybı:** `build_studio_cast.py` eski durumda tüm manifestleri, özellikle `approvals.json` dosyasını doğrudan yeniden yazabiliyordu. Artık aynı içeriğe dokunmuyor, farklı içeriği `FileExistsError` ile güvenli biçimde reddediyor. İnsan onayları otomatik sıfırlanamaz.
4. **Test kapsamı:** Esma'nın ayrı karakter dosyası ile manifestin tutarlılığı, görsel iş emri kapısı ve onay dosyalarının korunması için regresyon testleri eklendi.

## Açık doğrulama eksikleri
- Esra, Ahmet, Veysel, Öznur, Davut ve Fatoş gibi yetişkinlerin sayısal yaşlarının bir kısmı yaratıcı brief'te kesinlik taşımıyor; `age_years` alanları toplu sahip onayında yeniden kontrol edilmeli. Bu rapor yaşları onaylamaz.
- "Aden ailesi Harun'un evinde yaşıyor" ifadesi önceki hedef tanımında yer alıyor, fakat paket bunu `UNVERIFIED` olarak kaydetmiş. Sahip kanonunda teyit ve dosya provenance kaydı olmadan zorunlu sahne varsayımı hâline getirilmemeli.
- 48 iş emrinin AHOS gerçek iş kuyruğunda çalıştığı henüz doğrulanmadı. Dosya yolu beyanı teslim edilmiş dosya kanıtı değildir.
- Ses dosyalarının mevcut olması, doğal/robotik olmayan diksiyon ve uygun lisans kalite onayı değildir.
- Blender'in kurulmamış veya CUDA'nın bulunmamış olması, 16 karakter için metin hazırlığını engellemez ama gerçek 3D üretimin hazır olmadığı anlamına gelir.

## Bir sonraki gerçek ürün darboğazları
1. Ücretsiz ve kimlik koruyan görsel yolun teknik+lisans+gizlilik testini yap; özel medya harici servislere izinsiz gitmesin.
2. Onaylı karakter görüntüsü üretilene dek, 16 karakterin *tasarım spesifikasyonlarını* ortak inceleme paketinde sun.
3. 16 profil için ses QA'sı ve gerçek MP3/WAV kayıt kanıtlarını ayrı işle; ilk bölümün 34/38 replik sayısı metinden yeniden ölçülmeli.
4. Gerçek Blender ortamı (ücretsiz CPU çalışması mümkünse) küçük sahne ile kanıtlanmalı. Tek 3D boş dosya hazır karakter sayılmamalı.
5. Onay kapıları korunarak bölüm açılışı 30 saniyelik **gerçek MP4** ile doğrulanmadan tüm stüdyo READY kabul edilmemeli.

**Korunanlar:** v1 senaryo, bağımsız POC, S01E001 v2, özel medya, çalışan servisler ve önceki kullanıcı dosyaları.
**Harcama:** 0 €, yeni hesap/API yok, yeni render yok.
