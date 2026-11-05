# CLINE — Kanıt Kaydı

Bu dosya, Cline'ın (ve diğer ajanların) **gerçekten çalıştırdığı** komutların kanıt kaydıdır.
Burada karşılığı olmayan hiçbir iddia geçerli değildir (bkz. `AGENTS.md` §6).

## Format
```
## <tarih saat>
komut : <tam komut>
exit  : <kod>
çıktı : <ham stdout/stderr>
kaynak: <dosya> → <alan>=<değer>
```

## 2026-11-03 21:09 — Eğitim (referans kayıt)
komut : python -c "from ahos.training import teach; ..."
exit  : 0
çıktı : departman: 17 · çalışan: 81 · geçen: 81 · kalan: 0 · ortalama: %100.0 · süre: 0.344 sn
kaynak: ahos_core/config/training-report.json → passed=81, failed=0, average_score=100.0, generated_at=2026-11-03T21:09:45

## 2026-11-03 21:33 — Sağlık denetimi
komut : python -c "from ahos.health_guard import check; print(check(Path('runtime'), fix=True).to_dict())"
exit  : 0
çıktı : genel: SORUN VAR · servis:panel TimeoutError · daemon stopped (tick 108) · ofis 200 · tünel 200
kaynak: ahos_core/config/health-report.json → ok=false

## Render integration — 2026-11-05T18:10:21.972207+00:00
generated_at: 2026-11-05T18:10:21.972207+00:00
komut : python -B control_plane_v2/runtime/render-integration-20261105/install.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Set-Location ahos_core; python -m pytest -q --no-header --timeout=90 tests/test_render_task.py tests/test_llm_executor.py tests/test_render_integration.py tests/test_queue_drain.py
exit  : 1
çıktı :
```text
Installed source changes (no service restart): AGENTS.md, workflows/ltx2_text2video.json, workflows/ltx2_text2video.README.md, ahos_core/ahos/comfy_bridge.py, ahos_core/ahos/render_task.py, ahos_core/ahos/queue_drain.py, ahos_core/ahos/office_server.py, ahos_core/ahos/office_3d.py, ahos_core/tests/test_render_task.py, ahos_core/tests/test_render_integration.py
ERROR: usage: __main__.py [options] [file_or_dir] [file_or_dir] [...]
__main__.py: error: unrecognized arguments: --timeout=90
  inifile: C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\pyproject.toml
  rootdir: C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core
```
Durum: Kaynak uygulandı; testler başlamadı (--timeout desteklenmiyor). Servis yeniden başlatılmadı. Commit/push yapılmadı. T1-T6 kabulü doğrulanmadı.

## 2026-11-05T20:25:17+01:00 — A1–B3 kapsam/model/QA kabulü (Desktop Commander)
generated_at: 2026-11-05T20:25:17.6674534+01:00
kaynak: ahos_core/ahos/queue_drain.py → deterministic simple_edits + read-back QA; ahos_core/tests/test_scope_model_routing_acceptance.py → tmp_path acceptance

komut : cd ahos_core; python -m pytest -q --no-header tests/test_scope_model_routing_acceptance.py tests/test_queue_drain.py tests/test_simple_edits.py tests/test_llm_executor.py tests/test_model_fallback.py
exit  : 0
çıktı (ham stdout):
```text
...........................................                              [100%]
43 passed in 2.55s
TARGETED_EXIT=0
```

komut : cd ahos_core; python -m compileall -q ahos tests
exit  : 0
çıktı (ham stdout):
```text
COMPILE_EXIT=0
```

komut : cd ahos_core; python -m pytest -q --no-header tests --ignore=tests/test_daemon.py
exit  : 0
çıktı (ham stdout):
```text
........................................................................ [  6%]
........................................................................ [ 12%]
........................................................................ [ 18%]
........................................................................ [ 24%]
........................................................................ [ 30%]
........................................................................ [ 36%]
........................................................................ [ 42%]
........................................................................ [ 48%]
........................................................................ [ 54%]
........................................................................ [ 60%]
........................................................................ [ 67%]
........................................................................ [ 73%]
........................................................................ [ 79%]
........................................................................ [ 85%]
........................................................................ [ 91%]
........................................................................ [ 97%]
..............................                                           [100%]
1182 passed in 216.29s (0:03:36)
PYTEST_NON_DAEMON_EXIT=0
```

komut : cd ahos_core; python -m pytest -q --no-header tests
exit  : 2
çıktı (ham hata, ilgili satırlar):
```text
ERROR collecting tests/test_daemon.py
ImportError: cannot import name 'AutonomyDaemon' from 'ahos.daemon'
ERROR tests/test_daemon.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
PYTEST_EXIT=2
```
Not: daemon uyumsuzluğu bu A1–B3 değişikliğinden önce de vardı; tam pytest henüz kabul edilmiş sayılmaz.

komut : cd ahos_core; python -m pytest -q --no-header --timeout=60 tests
exit  : 4
çıktı (ham hata):
```text
ERROR: usage: __main__.py [options] [file_or_dir] [file_or_dir] [...]
__main__.py: error: unrecognized arguments: --timeout=60
  inifile: C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\pyproject.toml
  rootdir: C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core
PYTEST_EXIT=4
```

## 2026-11-05T21:25:44+01:00 — AHOS reality audit / taskboard + verified learning repairs
generated_at: 2026-11-05T21:25:44.4517455+01:00
source: ahos_core/reports/AHOS-REALITY-AUDIT-20261105.md
scope: no force push, no blanket queue reopen, taskboard migrated under OS lock with original bytes backed up

command: cd ahos_core; python ../tools/repair_taskboard_schema.py runtime/taskboard.json
exit: 0
raw stdout:
{"status": "legacy-empty-preview", "changed": false}
PREVIEW_EXIT=0

command: cd ahos_core; python ../tools/repair_taskboard_schema.py runtime/taskboard.json --apply
exit: 0
raw stdout:
{"status": "migrated", "changed": true, "backup": "runtime\\taskboard.json.backup-20261105T200740Z-424e5196"}
MIGRATE_EXIT=0

command: cd ahos_core; python ../tools/unlock_blocked.py 40
exit: 0
raw stdout:
{"dry_run": true, "candidates": 0, "planned": [], "moved_items": []}
No missions were marked complete; unrecoverable blocks remain blocked.
SAFE_TRIAGE_EXIT=0

command: cd ahos_core; python -m pytest -q --no-header tests
exit: 0
raw summary stdout:
1193 passed, 36 skipped in 200.85s (0:03:20)
FINAL_FULL_PYTEST_EXIT=0

command: cd ahos_core; python -m pytest -q --no-header tests/test_sovereign_evidence.py tests/test_ceo_powers.py tests/test_observed_learning.py tests/test_taskboard_schema_repair.py tests/test_office_3d.py
exit: 0
raw stdout:
........................                                                 [100%]
24 passed in 1.37s
LATEST_SUITE_EXIT=0

command: python -m compileall -q ahos_core/ahos ahos_core/tests tools/repair_taskboard_schema.py tools/unlock_blocked.py tools/triage-blocked.py
exit: 0
raw stdout:
COMPILATION_EXIT=0

command: git diff --check
exit: 0
raw status: DIFF_CHECK_EXIT=0 (CRLF conversion warnings; no whitespace errors)

Remaining: local ComfyUI port 8188 unavailable; GitHub hosted 30m cron has no access to local SQLite; stored owner hash is not cryptographic authorization.
