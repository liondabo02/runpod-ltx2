---
name: software-department
description: Yazılım Şirketi üretim sözleşmesi: ücretsiz araçlar, çıktılar ve kabul kuralı
---

# Yazılım Şirketi

Bu beceri, **Yazılım Şirketi** departmanının üretim sözleşmesini tanımlar.

## Ne zaman kullanılır

Yazılım Şirketi: Sahibin istediği yazılım ürünlerini tasarlamak, geliştirmek, test etmek ve yayına hazır hale getirmek.

## Ücretsiz araç seti

- pytest
- kabul kapısı (tools/check_offline.py)
- git worktree

## Beklenen çıktılar

- değişiklik özeti
- test sonucu
- geri alma planı

## Kabul kuralı

- Teslim, departmanın projesindeki `tools/check_offline.py` kapısından geçmeli.
- Belgeler `deliverables/` altına yazılır; en az bir markdown başlığı ve
  120 karakter içerik gerekir.
- Bağımsız QA kanıtı olmadan `completed` yazılmaz.
- Ücretli araç kullanılmaz; maliyet 0 $.

## Stüdyo motor geliştirme (çizgi film stüdyosunun yazılım ekibi)

Görev: stüdyonun motorlarını (senaryo, karakter, animasyon, ses, müzik, mekân, efekt, kamera,
yerelleştirme, QA, üretim) referans çizgi film seviyesine taşımak. Film üretmez; motoru geliştirir.

### Döngü (her iş için, sırayla)
1. `python tools/software_dept.py durum` — yetenek haritası (`studio/engine_capabilities.json`)
   kanıttan hesaplanır; öncelik: KANIT_BOZUK > YOK > TESTSIZ > KISMI. İş seçimi önce Project
   `claude/gorev_kuyrugu.md` (kilit kuralı), sonra bu listeden.
2. Kusuru önce ölç ve kanıtla (sayı, kare, komut çıktısı). Ölçülemeyen kusur için önce ölçü yaz.
3. Motoru genel düzelt: proje verisine (series/<id>/) özel sabit, koordinat, isim yok.
4. Kusuru yakalayan testi yaz. `python tools/software_dept.py kabul --test tests/test_x.py`:
   test yeni kodda GEÇMELİ, eski kodda (HEAD~1 ya da --base) DÜŞMELİ. Eski kodda da geçen test
   kusuru yakalamıyordur -> RED. Kırmızı adım yalnız gerekçeyle atlanır (--kirmizi-gerekmez).
5. Tam test paketi; commit (mesaj görev koduyla başlar, ör. "H23 ..."); fetch + gerekirse rebase;
   normal push; local == remote SHA doğrula. Force push, main'e merge, hard reset yok.
6. Yeni yetenek kazandıysan `studio/engine_capabilities.json`'a kanıtıyla ekle/güncelle ve
   `python tools/engine_gaps.py --write-skills` ile ilgili işçinin skill dosyasını yenile.
7. Rapor: tamamlanan davranış, sürüm ve kanıt, kapsam (birim/entegrasyon/render/uçtan uca ayrı),
   açık kusurlar, sıradaki iş, yalnız sahibin çözebileceği engeller.

### Ofiste görünme
Ofis yalnız gerçek kayıt gösterir. Daldaki commit'ler `python tools/software_dept.py ofis-senkron`
ile "Yazılım Şirketi"nin bitmiş işi olarak ofis olay kaydına işlenir (PC'de gece güncellemesinde).

### Sınırlar
- Teknik VAR, profesyonel kalite değildir; "insan onayı" işaretli yetenekte son söz sahiptedir.
- Ses dinlenemiyorsa ses kalitesi geçti sayılmaz. Motoru olmayan dil "destekleniyor" denmez.
- Ücretli API/GPU yalnız sahibin açık onayı, servis adı ve üst sınırıyla.

<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->
## Motorlar ve yetenekler (gerçek araçlar)

Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.
Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.

- YAZ-02 Kırmızı-yeşil kabul kapısı (test eski kodda düşer, yenide geçer) [VAR]: `tools/software_dept.py`
- YAZ-03 Departman işinin ofiste gerçek kayıtla görünmesi [VAR]: `tools/software_dept.py`
<!-- MOTORLAR:BITIS -->
