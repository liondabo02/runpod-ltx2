import io
import os
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

os.environ["AHOS_DOCUMENT_QA"] = "1"

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
DB = R / "company-service.db"

targets = (
    "CMD-marketing-tanitim-metni-a1",
    "CMD-research-oyun-onerileri-a1",
    "CMD-quality-kapi-raporu-a1",
    "CMD-finance-harcama-ozeti-a1",
    "CMD-data-kuyruk-raporu-a1",
)

con = sqlite3.connect(DB)
reset = 0
for mission in targets:
    cur = con.execute(
        "update missions set status='pending', last_error='', updated_at=datetime('now') "
        "where mission_id=? and status='blocked'",
        (mission,),
    )
    reset += cur.rowcount
con.commit()
print("yeniden açılan:", reset)

from ahos.owner_console import build_default_console
from ahos.queue_drain import drain

console = build_default_console(R)
results = drain(console, owner="dept-docqa", limit=5)
print("işlenen:", len(results))

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
for row in con.execute(
    "select mission_id, status, last_error from missions where mission_id in "
    "(?,?,?,?,?) order by mission_id",
    targets,
):
    print(f"  {row['mission_id'][:40]:40} {row['status']:10} {(row['last_error'] or '')[:70]}")

counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print("durum:", counts)
