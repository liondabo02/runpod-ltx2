import io
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
DB = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\company-service.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

rows = list(con.execute("select mission_id, status, updated_at from missions"))

bases = defaultdict(list)
for row in rows:
    base = re.sub(r"-r\d+$", "", row["mission_id"])
    bases[base].append(row)

collapsed = 0
for base, items in bases.items():
    if len(items) < 2:
        continue
    # En güncel kaydı bırak; diğer tekrarları cancelled yap.
    items.sort(key=lambda r: (r["updated_at"] or ""), reverse=True)
    for stale in items[1:]:
        if stale["status"] in {"completed"}:
            continue
        con.execute(
            "update missions set status='cancelled', "
            "last_error='tekrar (aynı hedef) - tekilleştirildi', "
            "updated_at=datetime('now') where mission_id=?",
            (stale["mission_id"],),
        )
        collapsed += 1

con.commit()
counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print("tekilleştirilen tekrar:", collapsed)
print("yeni dağılım:", counts)
