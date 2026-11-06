import io
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DB = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\company-service.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

BATCH = 10
rows = con.execute(
    "select mission_id, last_error from missions where status='blocked' "
    "and (last_error like '%worker execution failed%' or last_error is null or last_error='') "
    "order by updated_at asc limit ?",
    (BATCH,),
).fetchall()

print("yeniden açılacak:", len(rows))
for row in rows:
    con.execute(
        "update missions set status='pending', updated_at=datetime('now') where mission_id=?",
        (row["mission_id"],),
    )
con.commit()

counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print("yeni dağılım:", counts)
print("blocked kalan:", counts.get("blocked"), "| pending:", counts.get("pending"))
