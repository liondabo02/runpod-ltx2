# AHOS — Çalışma Sözleşmesi (ajanlar arası çakışmasız)

Bu belge, aynı depoda çalışan ajanların (DeepSeek/Claude/Codex) birbirinin işini
bozmadan ilerlemesi için bağlayıcı kuralları tanımlar. Kural: **kolaya kaçmak yok;
her değişiklik kanıtlı, testli ve sınırlı.**

## 1. Alan sınırları

| Alan | Sahip | Kural |
|---|---|---|
| `ahos_core/ahos/{ceo,ceo_brain,goals,product,experience,tasks,tracking,ideas,office,office_server,inbox,knowledge,skills,skilleval,infra,learning,failure_analytics,backup,brain,business_delivery,company_foundry}` | bu ajan | serbest |
| `control_plane_v2/runtime/AHOS-QUALITY-99` | Codex | **dokunulmaz** |
| `ahos-quality-99/releases` | Codex / bulut | **dokunulmaz** |
| `ahos_core/pyproject.toml`, `owner_console.py`, `autonomy.py`, `daemon.py`, `acceptance.py`, `project_qa.py`, `autonomous_company.py`, `control_plane_v2/AHOS-Daemon.ps1`, `AHOS-Watchdog.ps1` | paylaşılan | yalnız küçük, geri alınabilir değişiklik; önce `git diff` ve test |

Kontrol: `python tools/check_ownership.py` (staged dosyaları denetler).
Kanca kurulumu: `python tools/check_ownership.py --install` → ihlalde commit engellenir.

## 2. Çakışma önleme kuralları

1. **Yeni iş = yeni modül.** Var olan paylaşılan dosyayı büyütmek yerine ayrı modül
   yaz (`ceo_brain`, `tracking`, `goals`, `experience`…).
2. **Küçük ve tek amaçlı diff.** Aynı commit'te hem davranış hem refactor yok.
3. **Yazmadan önce oku.** Paylaşılan dosyada `edit` yalnız okunduktan sonra.
4. **Atomik yazma.** Durum dosyaları `tmp` + `replace` ile yazılır (yarım dosya yok).
5. **Silme yok.** Eski kayıtlar `.old`/arşiv olarak saklanır; "hiçbir şey silinmez".
6. **Commit öncesi kapı.** `python tools/check_ownership.py` + ilgili testler +
   tam paket yeşil değilse commit yok.

## 3. Kabul ölçütü

Bir iş "bitti" sayılmaz, ta ki:

- gerçek dosya değişikliği > 0,
- projenin kendi kabul kapısı (`tools/check_offline.py`) geçene kadar,
- testler yeşil olana kadar.

Tarayıcıda açılması teslim kanıtı değildir.

## 4. Kayıt

Her tur sonunda `quality/evidence/Q99-*.md`: ne yapıldı, ölçüm, kalan risk.
Karar ve gerekçe yazılır; "denendi" ile "geçti" ayrı yazılır.
