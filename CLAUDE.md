# AHOS Studio — Claude Code proje kuralları
- Dil: kullanıcıyla sade Türkçe. Kullanıcı kodcu değil; adım adım anlat.
- Bağlayıcı kurallar: force push yok, main'e merge yok, hard reset/git clean yok, izinsiz silme yok, kodda gizli anahtar yok, onaysız ücretli API/GPU yok, kalite eşiği düşürülmez, sahte PASS yok, AHOS-RIG-FACTORY-DS salt okunur.
- Teknik PASS ≠ profesyonel kalite. Motoru olmayan dili "destekleniyor" deme.
- Test: `python -m unittest discover -s tests`; sağlık: `python tools/agent_doctor.py`.
- Gözlem: sürtünme/düzeltme `python tools/task_observer.py log ...` ile kaydedilir (skills/task-observer).
- Rapor biçimi: FAZ/DURUM/MEVCUT DURUM/YAPILAN DEĞİŞİKLİK/DEĞİŞEN DOSYALAR/TEST KOMUTU/EXIT CODE/TEST SONUCU/COMMIT SHA/LOCAL==REMOTE/KALAN EKSİKLER/SONRAKİ ADIM.
- Kalite ölçüsü: `docs/2D_KALITE_STANDARDI.md`; ölç: `python tools/studio_standards_check.py --series-id <id> --episode <eN>`. Yaratıcı zevk sahibindedir, ölçüm "NOT_EVALUATED" yazar.
- Senaryo gelince: önce `script_to_beats` (sadık vuruşlar), sonra `script_enrich` (tepki/şaka/arka plan, onaya sunulur), ses `audio_polish`, müzik `score_engine`, efekt `fx_layer`. Replik/süre/karakter değiştirilmez.
- Aynı depoda başka ajanlar da çalışabilir: dosyayı yazmadan önce PC'deki sürümü karşılaştır (mtime korumalı yaz), başkasının değişikliğini ezme.
