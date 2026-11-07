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

## 2026-11-06 — P1: Project-local pytest acceptance gate

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header tests/test_acceptance_offline.py
exit  : 0
çıktı :
```text
...                                                                      [100%]
3 passed in 4.53s
P1_TEST_EXIT=0
```

komut : cd ahos_core\runtime\projects\holding-core; ..\..\..\..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header tests
exit  : 0
çıktı :
```text
ssssssssssssssssssssssssssssssssssss................                     [100%]
16 passed, 36 skipped in 0.61s
EXIT_CODE=0
```

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header --timeout=120 tests
exit  : 0
çıktı :
```text
........................................................................ [  5%]
........................................................................ [ 11%]
........................................................................ [ 17%]
......................................................................ss [ 23%]
ssssssssssssssssssssssssssssssssss...................................... [ 29%]
........................................................................ [ 34%]
........................................................................ [ 40%]
........................................................................ [ 46%]
........................................................................ [ 52%]
........................................................................ [ 58%]
........................................................................ [ 64%]
........................................................................ [ 69%]
........................................................................ [ 75%]
........................................................................ [ 81%]
........................................................................ [ 87%]
........................................................................ [ 93%]
........................................................................ [ 99%]
............                                                             [100%]
1200 passed, 36 skipped in 263.60s (0:04:23)
ALL_TESTS_EXIT=0
```

komut : ..\control_plane_v2\.venv\Scripts\python.exe -m py_compile ahos_core/ahos/acceptance.py ahos_core/ahos/project_qa.py ahos_core/tests/test_acceptance_offline.py ahos_core/tests/test_project_qa.py ahos_core/tests/test_autonomy.py
exit  : 0
çıktı :
```text
COMPILE_EXIT=0
```

komut : ..\control_plane_v2\.venv\Scripts\python.exe -m compileall -q ahos_core\ahos ahos_core\tests
exit  : 0
çıktı :
```text
SOURCE_COMPILE_EXIT=0
```

kaynak: ahos/acceptance.py → check_offline(project_root), ahos/project_qa.py → trusted_gate + check_offline.
Not: git-ignored runtime altındaki üçüncü taraf site-packages için tüm ahos_core'ı compileall yapmak Windows dosya yolu kaynaklı FileNotFoundError üretti; AHOS kaynak/test kodunun compileall kontrolü temizdir.

## 2026-11-06 — P1 work_path acceptance-root regression

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header --timeout=120 tests/test_project_qa.py tests/test_acceptance_offline.py tests/test_qa_integration.py
exit  : 0
çıktı :
```text
...............                                                          [100%]
15 passed in 4.54s
TEST_EXIT=0
COMPILE_EXIT=0
```

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header --timeout=120 tests/test_owner_console.py tests/test_project_qa.py tests/test_acceptance_offline.py
exit  : 0
çıktı :
```text
.................................................                        [100%]
49 passed in 9.65s
INTEGRATION_EXIT=0
```

kaynak: ahos/owner_console.py → bound_project.work_path, ahos/project_qa.py → make_project_qa(work_path), tests/test_project_qa.py → test_work_path_is_the_project_root_for_acceptance.

## 2026-11-06 — Queue drain plan-score feedback integration

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header --timeout=120 tests/test_observed_learning.py tests/test_queue_drain.py tests/test_scope_model_routing_acceptance.py
exit  : 0
çıktı :
```text
................                                                         [100%]
16 passed in 2.14s
PYTEST_EXIT=0
```

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -c "import runpy,tempfile,json,gc;from pathlib import Path;t=runpy.run_path('tests/test_observed_learning.py')['test_twenty_observed_tasks_score_more_than_ten_actual_workers'];tmp=tempfile.TemporaryDirectory();root=Path(tmp.name);t(root);scored=sum(bool(json.loads(p.read_text(encoding='utf-8'))['self_model'].get('plan_scores')) for p in (root/'minds').glob('software-worker-*.json'));print('MISSIONS=20 PLAN_SCORES_WORKERS='+str(scored));gc.collect();tmp.cleanup()"
exit  : 0
çıktı :
```text
MISSIONS=20 PLAN_SCORES_WORKERS=20
WORKER_ACCEPTANCE_EXIT=0
```

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header --timeout=120 tests
exit  : 0
çıktı (final) :
```text
........................................................................ [ 92%]
........................................................................ [ 98%]
...............                                                          [100%]
1203 passed, 36 skipped in 248.77s (0:04:08)
ALL_TESTS_EXIT=0
```

komut : ..\control_plane_v2\.venv\Scripts\python.exe -m py_compile ahos_core\ahos\queue_drain.py ahos_core\ahos\mind_feedback.py ahos_core\tests\test_observed_learning.py
exit  : 0
çıktı :
```text
PYCOMPILE_EXIT=0
```

kaynak: ahos/queue_drain.py → _scoring_worker ve score_plan çağrısı; ahos/mind_feedback.py → record_plan_score bayrağı; tests/test_observed_learning.py → 20 gerçek-işçi-ataması simülasyonu ve çift puanlama testi.
Not: 20 işçili kabul testi izole tmp_path ortamında sahte konsol ve gerçek SQLite + mind JSON dosyalarıyla koşar. Canlı runtime 20 ayrı çalışanı puanladı iddiası değildir.

## 2026-11-06 — commune.converse worker-last-task grounding

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header --timeout=120 tests/test_observed_learning.py
exit  : 0
çıktı :
```text
........                                                                 [100%]
8 passed in 1.41s
OBSERVED_TEST_EXIT=0
COMPILE_EXIT=0
```

canlı kaynak : ahos_core/runtime/company-service.db (salt okunur SQLite)
eşleşme      : result_json.steps[].worker_id + worker_summary (rastgele departman sahipliği YOK)
çıktı :
```text
DEPARTMENTS 17
ATTRIBUTED 37 DEPTS_WITH_WORKER_MISSIONS 17
READ_ONLY_CHECK_EXIT=0
LIVE_CONVERSE {'pairs': 34, 'messages': 68, 'departments': 17}
LIVE_LAST20_TOTAL 20 MISSION_ID_OBJECTIVE 20 WORKER_OWN_MISSIONS 20
LIVE_ACCEPTANCE_EXIT=0
NOW_LAST20 20 MISSION_ID_AND_OBJECTIVE 20
ACCEPTED True
RECHECK_EXIT=0
```

komut : cd ahos_core; ..\control_plane_v2\.venv\Scripts\python.exe -m pytest -q --no-header --timeout=120 tests
exit  : 0
çıktı :
```text
.....................                                                    [100%]
1209 passed, 36 skipped in 265.77s (0:04:25)
ALL_TESTS_EXIT=0
```

Kullanıcı kabulü: conversations.jsonl dosyasının son 20 satırında en az 10 gerçek mission_id ve kısaltılmış objective.
Sonuç: 20/20 (canlı runtime); izole tmp_path testi de 20/20.
Güvenlik: Terminal mission olmadan kişi adına geçmiş görev uydurulmaz; eksik eşleşmede departman kaynağı olarak ayrıca işaretlenir. Önceki kayıtlar silinmedi.

## 2026-11-06 — AHOS idle study fairness, mission cap and live audit

- Verified live: 17 departments, 81 rostered workers, all 81 worker mind files present.
- Queue snapshot varied under concurrent jobs: 245 pending earlier, 2 pending during live idle-study check. Both <=300; no manual deletion for the metric.
- Existing operational plan_scores: 42 distinct worker JSON files populated (96 JSON files including non-roster/metadata).
- Learning round robin: cursor persisted to runtime/learning/.cursor.json; 81 distinct simulated workers in 14 bounded 6-worker iterations. Real worker-metrics ISO times used to skip activity within 30 minutes; active agents are not mislabeled idle.
- Live test: 50 eligible idle agents studied; 31 active agents skipped; mission queue 2 -> 2, no new mission enqueued; 17-department roster.
- Daemon rate-cap path now independently runs bounded idle study, without bypassing mission quotas. This is deterministic micro-lesson generation, **not** model consciousness or empirically verified skill gain.

Focused test:
```text
23 passed in 3.48s
FOCUSED_EXIT=0
COMPILE_EXIT=0
14 passed in 4.95s
GUARD_TESTS_EXIT=0
```

Full AHOS test:
```text
1221 passed, 36 skipped in 174.67s (0:02:54)
ALL_TESTS_EXIT=0
```

Only tracked intended changes to daemon.py, self_learning.py, test_self_learning_rotation.py and this evidence in the present commit. Concurrent unrelated uncommitted agent files are left intact.

## 2026-11-06 — AHOS QA-grounded growth, owner invariance and peer support

Scope: `ahos/agent_growth.py`, `sovereign.py`, `daemon.py`, `self_learning.py`, `llm_executor.py`, related tests and AGENT-GROWTH.md.

Evidence contract:
- No model consciousness or sentience claim. Affective state is an explicit simulation.
- Harun remains fixed owner despite AHOS_OWNER environment changes; existing pledge mismatch/corruption blocks growth rather than being overwritten. The unkeyed hash is NOT authentication.
- Completed steps qualify only with independent QA and `delivery.verified=true`. Blocked steps yield failure analysis. Raw job/peer text is not injected into model prompts.
- Growth state is separate from primary minds, using atomic worker overlays and append-only peer-support and overflow archives. No mission creation or cancellation performed.
- Every nine-worker cycle uses a durable roster cursor. Peer mentorship is same-department, QA-backed and deduplicated.

Focused test:
```text
49 passed in 5.15s
FOCUSED_EXIT=0
COMPILE_EXIT=0
43 passed in 3.84s
FOCUS_EXIT=0
COMPILE_EXIT=0
12 passed in 6.65s
PROMPT_INTEGRATION_EXIT=0
```

AHOS full suite:
```text
1234 passed, 36 skipped in 182.65s (0:03:02)
ALL_TESTS_EXIT=0
```

Live runtime acceptance with read-only SQLite + persistent separate worker overlays:
```text
PENDING_BEFORE 0 PENDING_AFTER 0
GROWTH_RESULTS 9 cycles x 9 updated
GROWTH_FILES 81
MOODS {'curious': 47, 'focused': 33, 'cautious': 1}
WITH_OBSERVED_EVIDENCE 34
WITH_FAILURE_LESSONS 2
WITH_PEER_COACHING 2
OWNER_GUARD_HARUN True
LIVE_GROWTH_EXIT=0
```

Not verified: a genuinely conscious agent, independently trained model weights, genuine emotion, infallible security/obedience, or automatic success on all real-world tasks. Admin credentials, GitHub permissions and API authentication require separate secure handling.

## ECC reference verification
generated_at: 2026-11-07T08:22:29.292106+00:00

komut : C:\Users\esmak\AppData\Local\Programs\Python\Python312\python.exe -B -m pytest -q --no-header -p no:cacheprovider tests/test_ecc_reference.py tests/test_ceo_knowledge.py
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core
exit : 0
```text
............                                                             [100%]
12 passed in 5.51s
```

komut : C:\Users\esmak\AppData\Local\Programs\Python\Python312\python.exe -m py_compile ahos/ecc_reference.py ahos/knowledge.py
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core
exit : 0
```text
```

komut : git diff --check -- ahos_core/ahos/knowledge.py
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
exit : 0
```text
```

## V5 işçi katmanı (G013/G018/G019/G020)
generated_at: 2026-11-07T10:48:16

komut : -B -m pytest -q --no-header -p no:cacheprovider tests/test_v5_worker_layer.py tests/test_office_3d.py tests/test_agent_office.py tests/test_control_center.py tests/test_v5_worker_state.py tests/test_v5_worker_card.py
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core
exit : 0
```text
.................................                                        [100%]
33 passed in 8.87s
```

komut : tools/worker_layer_check.py
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
exit : 0
```text
{
  "base": "http://127.0.0.1:8766",
  "checks": [
    {
      "check": "roster 200",
      "ok": true,
      "detail": 200
    },
    {
      "check": "roster 81 işçi",
      "ok": true,
      "detail": 81
    },
    {
      "check": "roster alanları",
      "ok": true,
      "detail": 81
    },
    {
      "check": "agent-office 200",
      "ok": true,
      "detail": 200
    },
    {
      "check": "durum kodları geçerli",
      "ok": true,
      "detail": [
        "blocked",
        "collaborating",
        "idle",
        "learning",
        "offline",
        "researching",
        "reviewing",
        "waiting_approval",
        "waiting_dependency",
        "working"
      ]
    },
    {
      "check": "durum toplamı = işçi",
      "ok": true,
      "detail": {
        "sum": 81,
        "workers": 81
      }
    },
    {
      "check": "bilinmeyen işçi 47",
      "ok": true,
      "detail": 47
    },
    {
      "check": "kart 200",
      "ok": true,
      "detail": 200
    },
    {
      "check": "kart durumu geçerli",
      "ok": true,
      "detail": "idle"
    },
    {
      "check": "özel hafıza gizli",
      "ok": true,
      "detail": true
    },
    {
      "check": "kart sayfası 200",
      "ok": true,
      "detail": 200
    },
    {
      "check": "kart sayfası ismi taşır",
      "ok": true,
      "detail": 2359
    },
    {
      "check": "olmayan işçi 404",
      "ok": true,
      "detail": 404
    },
    {
      "check": "olmayan kart 404",
      "ok": true,
      "detail": 404
    },
    {
      "check": "panel 200",
      "ok": true,
      "detail": 200
    },
    {
      "check": "panel durum sütunu",
      "ok": true,
      "detail": null
    },
    {
      "check": "panel işçi kartı linkleri",
      "ok": true,
      "detail": {
        "links": 81,
        "roster": 81
      }
    },
    {
      "check": "panel bayat/kayıt yok işareti",
      "ok": true,
      "detail": null
    }
  ],
  "passed": 18,
  "failed": 0
}
```

komut : -m py_compile ahos/worker_state.py ahos/agent_office.py ahos/worker_card.py ahos/intelligence.py ahos/control_center.py ahos/office_3d.py
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core
exit : 0
```text

```

komut : diff --check
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
exit : 0
```text
warning: in the working copy of 'ahos_core/ahos/intelligence.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'ahos_core/ahos/worker_card.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'ahos_core/ahos/worker_state.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'ahos_core/config/CLINE-KANIT.md', LF will be replaced by CRLF the next time Git touches it
```

## V5 kuyruk kurtarma (G014)
generated_at: 2026-11-07T10:55:14

komut : -B -m pytest -q --no-header -p no:cacheprovider tests/test_queue_repair.py
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core
exit : 0
```text
..........                                                               [100%]
10 passed in 1.27s
```

komut : tools/unlock_blocked.py 20 --include-board --match sandbox-1793538772
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
exit : 0
```text
{"dry_run": true, "candidates": 0, "by_class": {}, "planned": [], "skipped_recovered": [{"old": "CMD-ai-platform-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-ai-platform-sandbox-1793538772-r2"}, {"old": "CMD-creative-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-creative-sandbox-1793538772-r2"}, {"old": "CMD-data-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-data-sandbox-1793538772-r2"}, {"old": "CMD-finance-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-finance-sandbox-1793538772-r2"}, {"old": "CMD-genel-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-genel-sandbox-1793538772-r2"}, {"old": "CMD-guvenlik-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-guvenlik-sandbox-1793538772-r2"}, {"old": "CMD-holding-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-holding-sandbox-1793538772-r2"}, {"old": "CMD-infrastructure-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-infrastructure-sandbox-1793538772-r2"}, {"old": "CMD-marketing-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-marketing-sandbox-1793538772-r2"}, {"old": "CMD-operations-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-operations-sandbox-1793538772-r2"}, {"old": "CMD-oyun-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-oyun-sandbox-1793538772-r2"}, {"old": "CMD-quality-sandbox-1793538772", "class": "board_schema", "reason": "already recovered as CMD-quality-sandbox-1793538772-r2"}], "moved_items": []}
No missions were marked complete; unrecoverable blocks remain blocked.
```

komut : sqlite3 doğrulama (sandbox-1793538772-r*)
cwd : C:\actions-runner\_work\runpod-ltx2\runpod-ltx2
exit : 0
```json
{"replayed": 13, "completed": 13, "delivery_verified": 13, "originals_still_blocked": 12, "documents_created_today": 39}
```
