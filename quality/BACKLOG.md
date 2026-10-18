# AHOS-QUALITY-99 — İş Listesi

Durum kodları: `[ ]` açık · `[x]` kanıtlı tamam · `[~]` devam ediyor · `[!]` engelli

## P0 — Kritik

- [x] **Q99-001 Ölçüm**: 15 alanın baseline'ı (`BASELINE.md`), izole worktree'de 508 test.
- [x] **Q99-002 Ücret defteri doğruluğu**: `paid_calls` artık `model-spend.jsonl`'dan okunuyor.
      Kanıt: `quality/evidence/Q99-002.md`.
- [ ] **Q99-003 Gerçek özellik üretimi**: deterministik katalog tükendi. Yerel model yolu ≥2 GiB RAM
      istiyor; şu an 1.5 GiB. Seçenekler: (a) RAM boşalınca `auto` mod ile dene, (b) ücretsiz uzak
      sağlayıcı için sahip onayı, (c) yeni deterministik yetenek kataloğu.
- [ ] **Q99-004 Çökme kurtarma (committed ağaç)**: yarım görev yeniden başlatmada çift çalışmamalı,
      kaybolmamalı. Başka ajanın `recovery.py` çalışması commit edilince entegre doğrulama yapılacak;
      çakışmamak için şimdilik yalnız test/kanıt katmanı yazılacak.
- [ ] **Q99-005 Panel tekilliği**: 8765/8766 aynı kodu ve durumu göstermeli; daemon heartbeat panelde
      görünmeli. `control_center.py` başka ajanın aktif dosyası — commit edilince ele alınacak.

## P1 — Yüksek

- [~] **Q99-006 Test kapsamı**: ölçüldü — toplam %83; kritik modüller %83-88. `local_ollama` %0→%73,
      `daemon` %74→%83. Kalan: `owner_cli` ve `source_context` 0%. Kanıt: `quality/evidence/Q99-006.md`.
- [x] **Q99-007 Codex–DeepSeek görev sözleşmesi**: `taskboard.py` + CLI; tek sahip, lease/heartbeat,
      kanıtsız kapanmayan görev; 11 test. Kanıt: `quality/evidence/Q99-007.md`.
      Kalan: konsol/daemon entegrasyonu ve diğer ajanın benimsemesi.
- [x] **Q99-008 Executor bütçe tavanı**: ücretli sağlayıcı `AHOS_ALLOW_PAID_LLM=1` olmadan yok sayılıyor;
      yerel ücretsiz profil serbest. Kanıt: `quality/evidence/Q99-008.md`.
- [~] **Q99-009 Android doğrulaması**: tarayıcı yüklemesi (Q99-014), CDP etkileşim (Q99-015) ve
      **49/49 etkinlik taraması** (Q99-016) tamam. Android APK/emülatör kanıtı yok.

## P2 — Orta

- [x] **Q99-010 Merkezî hata günlüğü**: `errors.py` + `ahos-errors` CLI + daemon entegrasyonu;
      traceback/görev kimliği/boyut döndürme. Kanıt: `quality/evidence/Q99-010.md`.
      Kalan: panelde gösterim (control_center commit edilince).
- [x] **Q99-011 Yük testi**: 100 sentetik görev → 1.97 sn, 100/100 tamam, kayıp/tekrar yok,
      tekrar oynatma idempotent. Kanıt: `quality/evidence/Q99-011.md`.
      Not: başka ajanın soak testi commit edilirse iki test birleştirilecek.
- [x] **Q99-013 Tarayıcı QA kapısı**: web görevleri statik denetimden sonra headless tarayıcıda
      yükleniyor; başarısızsa teslim engelleniyor, tarayıcı yoksa atlanıyor. Kanıt: `quality/evidence/Q99-013.md`.
- [x] **Q99-016 49 etkinlik taraması**: tüm kartlar CDP ile açıldı → **49/49 açık, 0 istisna**.
      Kanıt: `quality/evidence/Q99-016.md`.
- [~] **Q99-017 Mipiluna etiket kusuru**: kök neden bulundu (`play-games.js` ve `simulations.js`
      fallback'sız `ART_ICONS` kullanıyor). Patch hazır ve **izole kopyada doğrulandı**
      (undefined 6 → 0). Üretime uygulanmadı; sahip onayı bekliyor.
      Kanıt: `quality/evidence/Q99-017.md`, `quality/patches/mipiluna-undefined-icons.patch`.

- [x] **Q99-018 İşçi idempotentliği**: tüm deterministik yetenekler iki kez uygulandığında ikinci tur
      dosya değiştirmiyor; proje dışına yazmıyor. Kanıt: `quality/evidence/Q99-018.md`.

- [x] **Q99-019 Durum raporu**: `ahos-status` CLI tüm kalıcı kayıtları (daemon, otonomi, kota,
      teslimat, hata, pano) tek ekranda birleştiriyor. Kanıt: `quality/evidence/Q99-019.md`.

- [x] **Q99-020 `source_context` sınırları**: 8 test; kapsam %0 → %98 (UTF-8, boyut, test/sır
      atlama, çıktı sınırı, eşleşme yok). Kanıt: `quality/evidence/Q99-020.md`.

- [x] **Q99-021 Daemon bekçisi**: `AHOS-Watchdog.ps1` ölü/bayat daemon'ı yeniden başlatıyor,
      `watchdog.log` + `errors.jsonl`'a yazıyor. İzole testte pid 14348 → 25940. Kanıt: `Q99-021.md`.

## Kural

Bir iş ancak şu üçü varsa `[x]` olur: (1) kod, (2) yeşil test, (3) `quality/evidence/` altında komut+çıktı.
