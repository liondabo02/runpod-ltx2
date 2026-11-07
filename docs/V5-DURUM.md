# AHOS V5 — Görev Durumu (canlı)

| Görev | Durum | Kanıt |
|---|---|---|
| 001 İşçi kimliği/çalışma profili | PARTIAL | 81/81 profil yükleniyor; 10 hafıza katmanı migrasyonu tamam. Kimlik/araç/yetki/iş yükü/güven alanları henüz tam değil |
| 002 10 katmanlı hafıza | PARTIAL | `cognitive_memory`: working/episodic/semantic/procedural/long_term/shared/shared + task_context/error_memory/collaboration_memory; kayıt zarfı (memory_id, content_hash, version, confidence, verification) 81/81 migre; recall skoru kaynak güvenilirliği+güncellik+doğrulama kullanıyor. Görev sırasında recall kullanımı henüz sadece araç testinde |
| 003 Planlama/karar | PARTIAL | `build_plans`/`assess_task` delivery pilot preflight'ta gerçek görevde kullanıldı; 10 senaryoluk plan→uygulama→ölçüm zinciri yok |
| 004 Üstbiliş | PARTIAL | `assess_task` research/ask_help/safe_test/verify/proceed; gerçek yardım başlatma testi yok |
| 005 İşlevsel duygu | PARTIAL | 12 boyut mevcut (merak, araştırma, güven, temkin, sabır, motivasyon, iş birliği, toparlanma, iş yükü, kalite, belirsizlik, açıklık); karar politikası testli; simülasyon sınırı korunuyor |
| 006 Çalışma kişiliği | PARTIAL | `work_personality.py`: departman/role göre stil, plan tercihi, iletişim; yetki/harcama etkisi yok; aynı planlar farklı departmanda farklı sıralanıyor (test) |
| 007 Mesajlaşma altyapısı | PARTIAL | `message_bus.py`: 11 tip, tekrar bastırma, görev/çift tavanı, ack kalıcı, restart-dayanıklı; gerçek işçi yardımıyla uçtan uca bağlanmadı |
| 010 Departman beyinleri | PARTIAL | `department_brain.py`: müdür, işçiler, yetenek, kuyruk, engel, teslimat, paylaşılan bilgi, bağımlılık, haftalık oran; 2 departman testi geçti |
| 008 Kolektif problem çözme | PARTIAL | `project_run` 3 departmanlı gerçek pilot (creative/software/quality) + QA; işçi bilişi deterministik araç |
| 009 Departmanlar arası bilgi | PARTIAL | `share_knowledge` doğrulanmış kayıt + dedupe; gerçek görevde çapraz kullanım izleme yok |
| 010 Departman beyinleri | PARTIAL | `department_brain.py`: müdür, işçiler, yetenek, kuyruk, engel, teslimat, paylaşılan bilgi, bağımlılık, haftalık oran; 2 departman testi geçti |
| 011 17 departman gerçek çıktı | PARTIAL | Pilotla creative/software/quality çıktı+QA var; diğer 14 departman yok |
| 012 Otonom hedef→görev | PENDING | Initiative→queue kök nedeni analiz edilmedi |
| 013 Sürekli kontrollü çalışma | PENDING | İşçi durumları (learning vb.) yok |
| 014 Kuyruk güvenliği | PARTIAL | pending≤300, lease recovery, tamamlanmış koruma testli; 43 blocked/14 failed kök neden raporu yok |
| 015 47 kanıtsız işçi | PARTIAL | `worker_tasks.py` gerçek görev önerisi üretiyor; toplu yürütme yok |
| 016 Öğrenme etkisi | PARTIAL | Öncesi/sonrası ölçüm aracı var; yeterli örnek yok (0 ölçülmüş) |
| 017 Kendi hatasını düzeltme | PARTIAL | 20 sentetik senaryo geçti; geçmiş gerçek hatalardan zincir yok |
| 018 3D ofis canlı durum | PARTIAL | Ofis ve durum API'si var; durum eşleme testi yok |
| 019 İşçi kartı | PENDING | — |
| 020 CEO paneli | PARTIAL | `/intelligence` holding/güvenlik/teslimat/işçi tablosu; `unknown/stale` işaretleme yok |
| 021 Çizgi film pilotu | PASS | 34,022 sn gerçek MP4 + Almanca sürüm + poster + altyazı + bağımsız QA (RMS −22,93 dB); LTX-2 değil deterministik hat |
| 022 Teslimat kayıt sistemi | PARTIAL | manifest: artifact/mission/worker/dosya/sha/ffprobe/QA/teslim ayrımı; dashboard gerçek yolu gösteriyor; DB kayıt defteri yok |

Bu tablo her turda güncellenir; PASS yalnız ham test/komut kanıtıyla verilir.
