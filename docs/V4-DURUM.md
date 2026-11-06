# AHOS V4 — Görev Durumu (canlı)

| Görev | Durum | Kanıt |
|---|---|---|
| 001 Envanter | PASS | `tools/inventory_v4.py` → `docs/ENVANTER-V4.md`, `config/inventory-v4.json` (30 bileşen, 17 dept/81 işçi) |
| 002 Baseline + yedek | PASS | `docs/BASELINE-V4.md`; `vault-20261106T230337Z-41da47f9` verified=true, 2.507 dosya |
| 003 Hafıza katmanları | PARTIAL | `cognitive_memory`: episodic/semantic/procedural/working + long_term/meta_memory/shared/recall/conflict; 18 test; 81 profil yükleme testi G020’de |
| 004 Çoklu plan | PARTIAL | `build_plans()` en az 3 strateji, zorunlu alanlar + gerekçe; yürütme yoluna bağlanmadı |
| 005 Üstbiliş | PARTIAL | `assess_task()` research/ask_help/safe_test/verify/proceed kararları; 3 test; yürütme öncesi kapıya bağlanmadı |
| 006–020 | PENDING | Sıradaki turlar |

Bu tablo her turda güncellenir; PASS yalnız ham test/komut kanıtıyla verilir.
