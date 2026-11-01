import io
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row

prefixes = ("CMD-data-", "CMD-finance-", "CMD-guvenlik-", "CMD-quality-", "CMD-research-", "CMD-marketing-")
rows = list(con.execute("select mission_id, objective, status, last_error, updated_at from missions order by updated_at desc limit 40"))
print(f"{'MISSION':42} {'DURUM':10} NEDEN")
for row in rows:
    if not row["mission_id"].startswith(prefixes):
        continue
    reason = (row["last_error"] or "")[:90].replace("\n", " ")
    print(f"{row['mission_id'][:42]:42} {row['status']:10} {reason}")

counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print("\ndurum:", counts)
