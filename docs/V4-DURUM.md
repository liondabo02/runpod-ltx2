# AHOS V4 — Görev Durumu (canlı)

| Görev | Durum | Kanıt |
|---|---|---|
| 001 Envanter | PASS | `tools/inventory_v4.py` → `docs/ENVANTER-V4.md`, `config/inventory-v4.json` (30 bileşen, 17 dept/81 işçi) |
| 002 Baseline + yedek | PASS | `docs/BASELINE-V4.md`; `vault-20261106T230337Z-41da47f9` verified=true, 2.507 dosya |
| 003 Hafıza katmanları | PARTIAL | `cognitive_memory`: episodic/semantic/procedural/working + long_term/meta_memory/shared/recall/conflict; 18 test; 81 profil yükleme testi G020’de |
| 004 Çoklu plan | PARTIAL | `build_plans()` en az 3 strateji, zorunlu alanlar + gerekçe; yürütme yoluna bağlanmadı |
| 005 Üstbiliş | PARTIAL | `assess_task()` research/ask_help/safe_test/verify/proceed kararları; 3 test; yürütme öncesi kapıya bağlanmadı |
| 006 Gerçek görev kapsamı | PARTIAL | `tools/worker_tasks.py`: 47 kanıtsız işçi için rol bazlı gerçek görev önerisi üretiyor (dry-run 8/47); henüz toplu çalıştırma yapılmadı |
| 007 Hata öğrenme zinciri | PASS | `tests/test_failure_learning.py`: **20/20 senaryo** hata→yansıma→düzeltme→QA→doğrulanmış ders; eski yöntem korunuyor |
| 008 Beceri ölçümü | PARTIAL | `tools/skill_metrics.py`: 83 işçi, 34 koşu, 39 görev kaydı; ilk deneme/QA/hata tekrarı/süre/yeniden çalışma/yardım; işçi bazlı maliyet `null` (atfedilmiş kayıt yok) |
| 009 Boşta öğrenmenin etkisi | PARTIAL | Öncesi/sonrası karşılaştırma hesaplanıyor; **0 işçide yeterli örnek** (37 yetersiz, 2 kayıt yok) → iyileşme iddia edilmiyor |
| 010 Uzman yönlendirme | PASS | `expert_router.py` + `test_v4_collaboration.py`: **20 çapraz departman senaryosu** (yetenek, kanıt, iş yükü, aynı/çapraz departman gerekçeli) |
| 011 Gerçek yardımlaşma | PASS | `help_workflow.py`: **10 vaka** talep→öneri→bağımsız QA→ortak bilgi; kendi kendine doğrulama reddedildi |
| 012 Çok-departman projesi | PASS | `project_run.py`: creative→software→quality uçtan uca (izole tmp), QA düşünce bağımlı görev bloke, döngü reddi |
| 013 Duygu politikası | PASS | 9 boyut + `test_v4_emotion.py`: başarısızlık→ask_help, yük→drain, belirsiz→research; `authority_effect=none` |
| 014 Sahip güvenliği | PARTIAL | `harun` sabit + exclusive-create (yarış testi), panel same-origin/CSRF, GET salt-okunur; RunPod/Oracle erişim sınırları doğrulanmadı |
| 015 Kuyruk güvenliği | PASS | `test_v4_resilience.py` + kapasite testleri: expired lease recovery, **tamamlanmış görev replace ile geri açılamaz** (kural eklendi), iptal yönetimi, tek satır/çift görev yok |
| 016 Restart/dayanıklılık | PARTIAL | Zihin restart + bozuk hafıza koruma testleri; tam daemon çökme enjeksiyonu henüz yok (memory vault doğrulaması mevcut) |
| 017 Model yönlendirme | PASS | `task_routing.py`: **30 görev tipi**, deterministik→python, QA bağımsız, ücretli model yalnız açık onay + bütçe |
| 018 Deneysel model | PASS (fizibilite) | `finetune_feasibility.py`: 1.324 doğrulanmış görev, 1.179 tekrarlı hedef, GPU yok, dengesiz etiket → **eğitim yapılmadı**, gerekçeli rapor |
| 019–020 | PENDING | Sıradaki turlar |

Bu tablo her turda güncellenir; PASS yalnız ham test/komut kanıtıyla verilir.
