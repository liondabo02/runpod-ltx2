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
- [ ] **Q99-008 Executor bütçe tavanı**: `AHOS_EXECUTOR=model` iken ücretli sağlayıcı varsayılan
      reddedilsin; yerel/ücretsiz profil serbest.
- [ ] **Q99-009 Android doğrulaması**: APK üretimi/emülatör kanıtı yok; izole deneme + kayıt.

## P2 — Orta

- [ ] **Q99-010 Merkezî hata günlüğü**: tüm süreçler için tek `errors.jsonl` + panelde son 20 hata.
- [ ] **Q99-011 Yük testi**: 100 sentetik görev (başka ajanın soak testi commit edilince birleştirilecek).
- [ ] **Q99-012 Mipiluna yeni katalog**: kart/kabartma/erişilebilirlik dışında kalan gerçek çocuk
      deneyimi iyileştirmeleri (LLM olmadan yapılabilenler).

## Kural

Bir iş ancak şu üçü varsa `[x]` olur: (1) kod, (2) yeşil test, (3) `quality/evidence/` altında komut+çıktı.
