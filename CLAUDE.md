# AHOS Studio — Claude Code proje kuralları
- Dil: kullanıcıyla sade Türkçe. Kullanıcı kodcu değil; adım adım anlat.
- Bağlayıcı kurallar: force push yok, main'e merge yok, hard reset/git clean yok, izinsiz silme yok, kodda gizli anahtar yok, onaysız ücretli API/GPU yok, kalite eşiği düşürülmez, sahte PASS yok, AHOS-RIG-FACTORY-DS salt okunur.
- Teknik PASS ≠ profesyonel kalite. Motoru olmayan dili "destekleniyor" deme.
- Test: `python -m unittest discover -s tests`; sağlık: `python tools/agent_doctor.py`.
- Gözlem: sürtünme/düzeltme `python tools/task_observer.py log ...` ile kaydedilir (skills/task-observer).
- Rapor biçimi: FAZ/DURUM/MEVCUT DURUM/YAPILAN DEĞİŞİKLİK/DEĞİŞEN DOSYALAR/TEST KOMUTU/EXIT CODE/TEST SONUCU/COMMIT SHA/LOCAL==REMOTE/KALAN EKSİKLER/SONRAKİ ADIM.
