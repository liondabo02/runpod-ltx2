# AHOS Render — T1..T6 Ham Kabul Kanıtları

Tarih: 2026-11-05, Almanya yerel saati. Repo:
`C:\actions-runner\_work\runpod-ltx2\runpod-ltx2`
Dal: `feature/agent-control-plane`. Çalışma **yalnızca yerel/izole mock**.
Bu belgede aşağıdaki test çıktıları terminalin döndürdüğü metindir; ComfyUI gerçek render ÇALIŞTIRILMADI.

## T1 — AGENTS.md

Komut (PowerShell; ahos_core içinde):
```powershell
python -B -c "from pathlib import Path;f=Path('../AGENTS.md').read_text(encoding='utf-8-sig');print('SORMA_YAP','SORMA, YAP.' in f,'QUEUE',('kuyruga yaz' in f or 'kuyruğa yaz' in f),'PAID',('harcama' in f or 'harcamalar' in f));assert 'SORMA, YAP.' in f"
```
Ham stdout:
```text
SORMA_YAP True QUEUE True PAID True
```
Exit code: **0**.

## T2 — Workflow şablonu / ComfyUI

Komut:
```powershell
python -B -c "from ahos.comfy_bridge import fill_template; w=fill_template('workflows/ltx2_text2video.json',prompt='test');print('WORKFLOW_NODES',len(w));print('PLACEHOLDER_TYPES',type(w['4']['inputs']['width']).__name__,type(w['5']['inputs']['seed']).__name__);print('SAVE_CLASS',w['7']['class_type'])"
```
Ham stdout:
```text
WORKFLOW_NODES 7
PLACEHOLDER_TYPES int int
SAVE_CLASS SaveImage
```
Exit code: **0**.

**Önemli gerçek:** Bu şablon sözleşmedeki örnek ComfyUI grafıdır;
gerçek bir LTX-2 video/MP4 üretim grafı DEĞİLDİR.
`model.safetensors` uyumlu gerçek checkpoint ile değiştirilmelidir.

ComfyUI erişim kontrolü:
```powershell
curl.exe -sS --max-time 2 -o NUL -w "COMFY_HTTP:%{http_code}\n" http://127.0.0.1:8188/system_stats
```
Ham çıktı:
```text
curl: (28) Connection timed out after 2010 milliseconds
COMFY_HTTP:000
COMFY_CURL_EXIT=28
```
Curl exit code: **28** (beklenen, ComfyUI bağlantısı yok).
Gerçek render isteği gönderilmedi.

## T3 — Render executor

Komut:
```powershell
python -B -m pytest -q --no-header tests/test_render_task.py --tb=short
```
Ham stdout:
```text
.......                                                                  [100%]
7 passed in 0.20s
```
Exit code: **0**.

Başarılı sahte dosya, ComfyUI kapalı, boş çıktı, boş prompt,
dış klasör, sıfır bayt, medya olmayan çıktı negatif kontrolleri mevcut.

## T4 — render: görev rotası

Komut:
```powershell
python -B -m pytest -q --no-header tests/test_render_integration.py --tb=short
```
Ham stdout:
```text
..                                                                       [100%]
2 passed in 0.81s
```
Exit code: **0**.

Test `render: ormanda minipula` görevinden sahte executor'a yönlendirmeyi;
iki işçi adımı için **tek** render çağrısı yapıldığını ve gerçek QA
olmayan sonuçların BLOCKED bırakılabildiğini doğrular.

## T5 — Ofis render listesi / dosya erişimi

T4 ile aynı `tests/test_render_integration.py` testi içindeki ikinci
senaryo `/ofis3d`, `/api/renders`, `/renders/<ad>`, dizin geçişi
ve yanlış uzantı reddini izole HTTP sunucusunda doğrular.

Ham stdout ve exit code: **T4 ile aynı**, `2 passed in 0.81s`, **0**.

## T6 — Roster / konuşma / TTS

Komut:
```powershell
python -B -c "import json;from pathlib import Path;d=json.loads(Path('config/roster.json').read_text(encoding='utf-8')); print('ROSTER_COUNT',len(d));print('WORKER_ID_PRESENT','oyun-manager' in d);print('FIELDS_OK',all('name' in v and 'title' in v for v in d.values()))"
```
Ham stdout:
```text
ROSTER_COUNT 81
WORKER_ID_PRESENT True
FIELDS_OK True
```
Exit code: **0**.

`test_render_integration.py` ayrıca `/api/roster` ve
`/api/talk?worker=oyun-manager&msg=neden` için 200 ve JSON `reply` test eder.
`office_3d.py` içinde `speechSynthesis` uygulanmıştır; sesin
kullanıcının gerçek tarayıcısında duyulduğu ayrıca manuel incelenmelidir.
Tarayıcıda gerçek TTS ses cihazı kontrolü yapılmadı.

## Zorunlu ve genişletilmiş testler

İstenen `--timeout=90` doğrudan pytest'te desteklenmiyor:
```text
ERROR: usage: __main__.py [options] [file_or_dir] [...]
__main__.py: error: unrecognized arguments: --timeout=90
EXIT_CODE=4
```
`pytest-timeout` kurulu olmadığından **Python subprocess ile 90 saniyelik gerçek
işlem zaman aşımı** uygulandı (süre verilmeden test atlanmadı).

Komut özeti:
```powershell
python -B -m pytest -q --no-header tests/test_render_task.py tests/test_llm_executor.py
```
Ham stdout:
```text
...........................                                              [100%]
27 passed in 1.61s
EXIT_CODE 0
SHELL_EXIT_CODE=0
```

Genişletilmiş kapsam:
```powershell
python -B -m pytest -q --no-header tests/test_comfy_bridge_safety.py tests/test_render_task.py tests/test_render_integration.py tests/test_llm_executor.py tests/test_queue_drain.py --tb=short
```
Ham stdout:
```text
.......................................                                  [100%]
39 passed in 2.67s
EXIT_CODE=0
```

Derleme:
```powershell
python -B -m py_compile ahos/render_task.py ahos/comfy_bridge.py ahos/office_3d.py ahos/office_server.py
```
Ham stdout:
```text
EXIT_CODE=0
```

## Çakışma / açık konular

- `owner_console.py` ve `ahos_core/config/CLINE-KANIT.md` başka
  çalışmanın commit edilmemiş dosyalarıdır; bu değişikliklere dokunulmadı,
  T1–T6 commit'ine dahil edilmedi.
- İstenen iş hedefinde ComfyUI çalışmadığı için GPU/render denenmedi.
- Grafik `SaveImage` üretir, gerçek LTX-2/MP4 üretimi doğrulanmadı.
- Render çıktısı ancak ayrıca medya ve bağımsız QA doğrulaması sonrası
  yayın kalitesinde kabul edilmelidir.
- Ayrı kaynak denetiminde `test_source_guards.py`, `worker_mind.py`
  dosyasını okuyamadığı için **1 unrelated fail / 22 pass** verdi;
  kaynakta U+FEFF BOM belirlendi. Tek-hedef kuralı gereği `worker_mind.py`
  değiştirilmedi. Bu, ilgili kaynak-güvenlik paketi için AÇIK hatadır.
- Rapor yalnızca **T1–T6 render/ofis entegrasyonunu** kapsar;
  bütün AHOS Holding'in eksiksiz olduğunu iddia etmez.
