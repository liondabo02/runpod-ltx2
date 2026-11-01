import io
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")

print("=== DEPARTMANLAR ===")
book = R / "departments.json"
if book.exists():
    data = json.loads(book.read_text(encoding="utf-8"))
    deps = data.get("departments") or data
    if isinstance(deps, dict):
        deps = list(deps.values())
    for dep in deps[:12]:
        if not isinstance(dep, dict):
            continue
        print(f"  {dep.get('department_id') or dep.get('id')} · {dep.get('name','')} · "
              f"işçi={len(dep.get('workers') or [])}")

print("\n=== İŞÇİ METRİKLERİ ===")
metrics = R / "worker-metrics.json"
if metrics.exists():
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    rows = payload.get("workers") if isinstance(payload, dict) else payload
    if isinstance(rows, dict):
        rows = list(rows.values())
    for row in (rows or [])[:10]:
        print(f"  {row.get('worker_id')}: koşu={row.get('runs')} başarı={row.get('success')} "
              f"ort={row.get('avg_ms')}ms")
else:
    print("  worker-metrics.json yok")

print("\n=== ÖĞRENME / GELİŞİM ===")
state = R / "daemon-state.json"
if state.exists():
    data = json.loads(state.read_text(encoding="utf-8"))
    print("  daemon:", data.get("status"), "| tick:", data.get("ticks"))
    print("  learning:", json.dumps(data.get("learning") or {})[:200])
    print("  quality:", json.dumps(data.get("quality") or {})[:200])
lessons = list(R.glob("knowledge/lessons*.jsonl")) + list(R.glob("**/lessons*.jsonl"))
print("  ders dosyası:", len(lessons))

print("\n=== DEPARTMAN BAZINDA KUYRUK ===")
con = sqlite3.connect(R / "company-service.db")
for row in con.execute(
    "select substr(mission_id,5,12) d, status, count(*) from missions "
    "where status!='cancelled' group by d, status order by 3 desc limit 12"
):
    print("  ", row[0], row[1], row[2])
