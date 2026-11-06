# Bilişsel katman — kapsam ve dürüst sınırlar

Bu belge, `ahos_core/ahos/cognitive_memory.py` ile eklenen katmanın ne
yaptığını ve **ne yapmadığını** kaydeder.

## Ne var

| Yetenek | Uygulama | Kanıt kuralı |
|---|---|---|
| Episodic memory | `runtime/cognition/<worker>.json` → `memory.episodic` | Yalnız QA kaydı olan görevler; `evidence_ok` alanı zorunlu |
| Semantic memory | `memory.semantic` | `verified=False` kayıt **reddedilir** (`ValueError`) |
| Procedural memory | `memory.procedural` (plan tipi → ok/fail/rate) | Yalnız gözlenmiş sonuç |
| Working memory | `memory.working` (aktif görev + adımlar) | Görev bitince `clear_working` |
| Goal planning | `plan_goal()` — seçenekleri puanlar, gerekçeli seçer | Plan, yürütme kanıtı sayılmaz |
| Metacognition | `metacognition()` — Laplace düzeltmeli güven, kalibrasyon açığı | Kanıtlı olay yoksa "no verified evidence" |
| Causal reasoning | `classify_cause()` — hata metninden neden sınıfı | Yalnız kayıtlı hata metni |
| Reflection | `reflect()` — ders + mission_id + kanıt bayrağı | Kanıtsızsa "kanıt yok" yazar |
| İşlevsel duygu | `emotion()` / `emotion_priority()` — 7 boyut, 0..1 | Yetki/harcama etkisi `none` |
| Kolektif zeka | `expert_index`, `find_expert`, `handoff`, `peer_review`, `mentor_pairs` | Paylaşım `verified=False` ise başarı sayılmaz |

## Ne yok (iddia edilmez)

- Gerçek bilinç, öznel duygu veya insan benzeri deneyim **yoktur**. "Duygu"
  burada öncelik/strateji etiketidir; yetki, bütçe veya güvenlik kuralı
  değiştirmez.
- Model fine-tuning / LoRA **yapılmaz**. `tools/eval_learning.py` yalnız iki
  karar politikasını ayrı bir değerlendirme kümesinde karşılaştırır; üretim
  modeline ağırlık yazmaz. B daha kötü çıkarsa `rollback_recommended: true`
  raporlanır.
- "Her işçi öğrendi" denmez: 81 profilin 47'si açıkça
  `no_verified_evidence` durumundadır.

## Kullanım

```bash
python tools/cognition_init.py            # kuru
python tools/cognition_init.py --apply    # 81 profil + uzman/mentor indeksi
python tools/cognition_sync.py --once     # yeni biten görevleri artımlı işle
python tools/eval_learning.py             # A/B politika değerlendirmesi
python tools/acceptance_advanced.py       # 10 kabul testi (--full: tüm paket)
```

`tools/cognition_sync.py` servis olarak 60 sn'de bir çalışır
(`control_plane_v2/AHOS-Cognition-Sync.ps1`, `AHOS-Baslat.cmd` 6. adım) ve her
yeni doğrulanmış görevi ilgili işçilerin profiline yazar; mission_id ile
tekilleştirir, tekrar koşuda 0 yeni kayıt üretir.

`tools/collective_loop.py` 5 dk'da bir uzman indeksini + mentor eşleşmelerini
tazeler ve engelli görevler için **devir önerisi** üretir
(`verified=false`, başarı sayılmaz; `AHOS-Baslat.cmd` 7. adım).

## Sahip güvenliği

`ahos_core/ahos/owner_auth.py`: PBKDF2 parola, süreli/kapsamlı oturum,
sabit zamanlı karşılaştırma, ayrıcalıklı işlem denetimi ve `SecureApprovalGate`.
Ajan aktörü onay veremez; deneme `runtime/owner/audit.jsonl` dosyasına yazılır.

Panel entegrasyonu (`panel_auth.py` + `control_center.py`):
- `/owner/login` → giriş; ilk kullanımda `/owner/login` **kurulum** formu gösterir
  (Harun parolayı belirler, en az 12 karakter).
- Oturum `HttpOnly; SameSite=Lax` çerezle taşınır; kapsamlar
  `approvals + authority + stop` ile sınırlıdır.
- Onay, red, acil durdurma, otonomi ve komut eylemleri geçerli oturum ister;
  oturum yoksa `303 → /owner/login?next=...` ve denetim kaydı yazılır.
- 5 hatalı giriş → 5 dakika kilit (`LoginThrottle`).
