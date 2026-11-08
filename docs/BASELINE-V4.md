# AHOS V4 — Başlangıç Durumu ve Geri Dönüş Planı (G002)

## Git durumu

| Alan | Değer |
|---|---|
| Branch | `feature/agent-control-plane` |
| HEAD | `b5bfd15b4e421a475591d2cf310e56fa2607caa1` |
| main (yerel = uzak) | `973ce5e4b3945cfc8d39f8b559838189dd7f6faa` |
| Force push | Yok (kural) |

Çalışma ağacında yalnız otomatik üretilen dosyalar değişik:
`ahos_core/config/health-report.json`, `ahos_core/config/training-report.json` ve
`ahos_core/--runtime-dir/` (eski daemon argüman hatasından kalan boş dizin).
Bunlar bu çalışmanın parçası değil; commit edilmez.

## Başka ajanların değişiklikleri

- Codex/ChatGPT commit’leri: `b5bfd15` (sahip kaydı + hafıza API koruması),
  `1fd1f6e` (memory vault), `3e069c9` (yedek sayımı), `a6d1630` (agent growth).
- Bu oturumun commit’leri: `ad4586e`, `51ff0af`, `64da451`, `470a300`, `95158b0`.
- Codex’in aktif düzenlediği dosya yok; çalışma ağacı temiz (yukarıdaki otomatik
  dosyalar hariç). Yeni çalışmalar ayrı commit’lerde ve yalnız ilgili dosyalarla
  yapılır (kural 8).

## Doğrulanmış yedek (G002)

- Araç: `ahos_core/ahos/memory_vault.py` (SQLite backup API + ZIP + SHA-256).
- Komut: `memory_vault.snapshot(runtime, default_backup_root())`
- Snapshot: `C:\actions-runner\_work\AHOS_BACKUPS\vault-20261106T230337Z-41da47f9`
- Doğrulama: **verified=true**, 2.507 dosya, SQLite 8.065.024 bayt.
- Mevcut diğer yedekler: `vault-20261106T214642Z-100aac08`, `2026-11-06_221440`,
  `2026-11-06_214100`.

## Geri dönüş planı

1. Kod geri alma: `git revert <commit>` veya main worktree’de `git reset --hard <önceki SHA>`
   (force push yok; main’e normal revert push edilir).
2. Veri geri alma: yalnız Harun onayıyla, `memory_vault.verify(snapshot)` sonrası
   snapshot’taki `company-service.db` ve `minds/` kopyalanır; canlı üzerine yazmadan
   önce yeni bir snapshot alınır.
3. Servis geri alma: daemon/panel/araştırma/bilişsel senkron/kolektif döngü
   `AHOS-Baslat.cmd` ile yeniden başlatılır; PID’ler `runtime/*.pid` ve
   `daemon-state.json` üzerinden doğrulanır.

## Başlangıç metrikleri (kanıt)

- 17 departman · 81 işçi · 96 zihin dosyası · 81 bilişsel profil.
- `plan_scores` dolu işçi: 42.
- Kanıtlı profil: 34 · kanıtsız: 47.
- Kuyruk: completed 4015 · blocked 43 · cancelled 1378 · failed 13 · pending 0.
- Sahip kurulumu: **yapılmadı** (parolayı yalnız Harun belirler).
- Çalışan servisler: daemon, control_center, office_server, research_loop,
  cognition_sync, collective_loop.

## Bilinen riskler

1. Sahip parolası henüz kurulmadı → ayrıcalıklı panel eylemleri girişe yönleniyor
   (güvenli varsayılan, işlevsel eksik değil).
2. 47 işçinin doğrulanmış görev kanıtı yok; sahte kayıtla doldurulmayacak.
3. Codex’in bazı çalışmaları (ör. `--runtime-dir` artığı) temizlenmedi; bu çalışma
   kapsamında silinmedi (kural 3).
