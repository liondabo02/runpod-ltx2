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
