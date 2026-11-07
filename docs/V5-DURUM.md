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
| 008 Kolektif problem çözme | PARTIAL | `project_run` 3 departmanlı gerçek pilot (creative/software/quality) + QA; işçi bilişi deterministik araç |
| 009 Departmanlar arası bilgi | PARTIAL | `share_knowledge` doğrulanmış kayıt + dedupe; gerçek görevde çapraz kullanım izleme yok |
| 010 Departman beyinleri | PARTIAL | `department_brain.py`: müdür, işçiler, yetenek, kuyruk, engel, teslimat, paylaşılan bilgi, bağımlılık, haftalık oran; 2 departman testi geçti |
| 011 17 departman gerçek çıktı | PARTIAL | 17/17 departmanın en az bir **doğrulanmış** teslimi var; bugün 12 departman pano engelinden kurtarılıp **39 gerçek belge** üretti (brief + doküman + QA review, `docs/KUYRUK-KURTARMA.md`). Derin alan çıktısı (hukuk analizi, finans modeli, kod) hâlâ yok |
| 012 Otonom hedef→görev | PARTIAL | `goal_intake.py`: yalnız **Harun onaylı** hedef → 3 plan → görev grafiği → kuyruk; idempotent (4 test). Forensik: initiative 1 kayıt/2,5 gün eski; yürütme+QA kapanışı henüz bağlı değil |
| 013 Sürekli kontrollü çalışma | PASS | `worker_state.derive()`: 10 durum; gözlem > taze olay (30 dk) > son koşu (24 sa) > "kayıt yok". Canlıda 81 işçi = **34 boşta · 47 çevrimdışı/kayıtsız · 0 çalışan** (bugün görev koşmadı); `/api/agent-office` `state_code` taşıyor; 12 test |
| 014 Kuyruk güvenliği | PASS | pending≤300, lease recovery, tamamlanmış koruma; **12 pano kaynaklı engel** yeni kimlikle tekrarlandı → **13/13 completed, delivery.verified=1**, orijinaller blocked kaldı; tekrar **idempotent** (tamamlanmış çocuk varsa 0 aday) ve pano bozuksa **fail-closed**; 10 test. Kalan 25 (20 kriz kopyası + 3 bağlamı değişmiş düzenleme + 2 Ar-Ge) elle incelemeye bırakıldı |
| 015 47 kanıtsız işçi | PARTIAL | `worker_tasks.py` gerçek görev önerisi üretiyor; toplu yürütme yok |
| 016 Öğrenme etkisi | PARTIAL | Öncesi/sonrası ölçüm aracı var; yeterli örnek yok (0 ölçülmüş) |
| 017 Kendi hatasını düzeltme | PARTIAL | 20 sentetik senaryo geçti; geçmiş gerçek hatalardan zincir yok |
| 018 3D ofis canlı durum | PASS | `/api/roster` **81 kayıt** (önce 404 idi; 3D ad yedeği çalışmıyordu), `/api/agent-office` `state_code`+`stale`+`unknown`, 3D incelemede durum gerekçesi ve **`/worker/<id>` kart linki**; eşleme testi 5 |
| 019 İşçi kartı | PASS | `worker_card` + `/api/worker-card/<id>` + `/worker/<id>` HTML; panelde **81 kart linki**, 3D incelemede "İşçi kartını aç →"; özel hafıza gizli (varsayılan), XSS kaçışı ve 404 testli |
| 020 CEO paneli | PASS | `/intelligence`: durum kartı **çalışan/boşta/çevrimdışı = 0/34/47**, **Durum sütunu**, "eski"/"kayıt yok" işaretleri, 81 işçi kartı linki; HTTP 200 · 26.9 KB |
| 021 Çizgi film pilotu | PASS | 34,022 sn gerçek MP4 + Almanca sürüm + poster + altyazı + bağımsız QA (RMS −22,93 dB); LTX-2 değil deterministik hat |
| 022 Teslimat kayıt sistemi | PARTIAL | `artifact_registry.py`: SQLite kayıt defteri; dosya/SHA/QA/teslimat ayrı; manifest dışı kanıt yok. Gerçek pilot `ADEN-PILOT-001` kaydedildi → **verified=true**, 1.746.064 bayt, hash eşleşti; 3 test geçti |

Bu tablo her turda güncellenir; PASS yalnız ham test/komut kanıtıyla verilir.
