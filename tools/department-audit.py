import io
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")

book = json.loads((R / "departments.json").read_text(encoding="utf-8"))
deps = book.get("departments") if isinstance(book, dict) else book

con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row

# mission_id formatı: CMD-<dept>-<slug>-<hash>[:step]
dept_stats = defaultdict(lambda: {"completed": 0, "blocked": 0, "pending": 0, "last": ""})
for row in con.execute("select mission_id, status, updated_at from missions where status != 'cancelled'"):
    mission = row["mission_id"].split(":")[0]
    parts = mission.split("-")
    key = parts[1] if len(parts) > 1 else "?"
    dept_stats[key][row["status"]] = dept_stats[key].get(row["status"], 0) + 1
    if row["updated_at"] and row["updated_at"] > dept_stats[key]["last"]:
        dept_stats[key]["last"] = row["updated_at"]

print(f"{'DEPARTMAN':16} {'İŞÇİ':>4} {'TAMAM':>6} {'ENGEL':>6} {'BEKLEYEN':>8}  SON AKTİVİTE")
for dep in sorted(deps, key=lambda d: d.get("department_id", "")):
    did = str(dep.get("department_id"))
    st = dept_stats.get(did, {})
    workers = len(dep.get("workers") or [])
    print(f"{did:16} {workers:>4} {st.get('completed',0):>6} {st.get('blocked',0):>6} "
          f"{st.get('pending',0):>8}  {(st.get('last') or '-')[:19]}")

print("\nEşleşmeyen kuyruk kalemleri (eski/geçici departmanlar):")
known = {str(d.get("department_id")) for d in deps}
for key, st in dept_stats.items():
    if key not in known:
        print(f"  {key:16} tamam={st.get('completed',0)} engel={st.get('blocked',0)}")
