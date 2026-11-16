---
name: studio-longform-production
description: Çok sahneli, uzun bölüm üretimini job ledger, resume ve bütçe sınırlarıyla yönetme
when_to_use: 30 saniyeden uzun veya 8 dakikalık çok sahneli bölüm üretileceğinde.
---

# Studio Longform Production

## Girdi
- Bölüm senaryosu, sahne/shot listesi, cast, süre
- Episode bütçesi ve provider politikası

## Prosedür
1. Her sahne/shot/replik için deterministik `job_id` üret.
2. `production_jobs` defterine `PENDING` yaz; bağımlılıkları bağla.
3. Sahne bazında üret; başarılı shot'ı yeniden üretme.
4. Hata sınıfına göre retry/fallback/block uygula; `maxfail` ve bütçe cap'ini aşma.
5. Kesinti sonrası yalnız `PENDING`/expired `RUNNING` işleri sürdür.
6. Montaj öncesi süre, ses ve motion kapılarını çalıştır.

## Kabul
- Toplam süre senaryoyla ±0.5 sn.
- Her shot gerçek video; tekrar/statik sahne yok.
- Bölüm yeniden başlatıldığında tamamlananlar korunur.
- `PRODUCTION_READY` yalnız bağımsız QA + owner onayıyla.

## Yasak
- 1 dakikalık klibi döngüyle 8 dakika saymak.
- Başarısız sahnede tüm bölümü baştan üretmek.
- Bütçe aşımını gizlemek.
