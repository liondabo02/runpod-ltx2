import io
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row

print("=== KUYRUK (tümü) ===")
counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print(counts)
real = sum(v for k, v in counts.items() if k != "cancelled")
print(f"gerçek toplam {real} · teslim %{100*counts.get('completed',0)/max(1,real):.1f}")

since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
row = con.execute(
    "select sum(case when status='completed' then 1 else 0 end), count(*) from missions "
    "where status!='cancelled' and updated_at >= ?",
    (since,),
).fetchone()
print(f"son 24s: {row[0]}/{row[1]} = %{100*row[0]/max(1,row[1]):.1f}")

print("\n=== DEPARTMAN (son 24s) ===")
for r in con.execute(
    "select substr(mission_id,5,12) d, "
    "sum(case when status='completed' then 1 else 0 end) ok, "
    "sum(case when status='blocked' then 1 else 0 end) bl, count(*) n "
    "from missions where status!='cancelled' and updated_at >= ? group by d order by n desc limit 12",
    (since,),
):
    print(f"  {r['d']:14} tamam={r['ok']:3} engel={r['bl']:3} toplam={r['n']:3}")

print("\n=== İŞÇİ (son 4000 kayıt) ===")
stats = {}
ledger = R / "worker-metrics.jsonl"
if ledger.exists():
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-4000:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = row.get("worker_id")
        item = stats.setdefault(key, [0, 0])
        item[0] += 1
        item[1] += 1 if row.get("success") else 0
    ranked = sorted(stats.items(), key=lambda kv: -kv[1][0])[:8]
    for worker, (runs, ok) in ranked:
        print(f"  {worker:28} koşu={runs:4} başarı=%{100*ok/max(1,runs):5.1f}")

print("\n=== AR-GE ===")
arge = R / "arge-state.json"
if arge.exists():
    payload = json.loads(arge.read_text(encoding="utf-8"))
    print("son tur:", payload.get("last_at"), "| zayıf:", payload.get("weakest"), "| ders:", payload.get("lessons"))

print("\n=== DEPARTMAN SAYISI ===")
book = json.loads((R / "departments.json").read_text(encoding="utf-8"))
deps = book.get("departments") if isinstance(book, dict) else book
print("departman:", len(deps), "| işçi tanımı:", sum(len(d.get("workers") or []) for d in deps))
