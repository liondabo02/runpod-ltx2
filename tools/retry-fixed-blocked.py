"""Düzeltmelerden ÖNCE engellenen görevleri sınırlı biçimde yeniden dene.

Seçim: worker_failed / mission_timeout / executor_missing / target_missing
sınıfındaki engelliler (QA reddi olanlar hariç — onlar gerçek kalite hatası).
Tur başına en fazla N görev; geçmiş korunur (attempts artırılır).
"""

import io
import sqlite3
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
DB = R / "company-service.db"
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 8

from ahos.failure_analytics import classify_error

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

candidates = []
for row in con.execute(
    "select mission_id, last_error, attempts, max_attempts from missions where status='blocked' "
    "order by updated_at asc"
):
    cause = classify_error({"message": row["last_error"] or ""})
    if cause in {"worker_failed", "mission_timeout", "executor_missing", "target_missing"}:
        candidates.append((row["mission_id"], cause))
    if len(candidates) >= BATCH:
        break

print("yeniden açılacak:", len(candidates))
reopened = []
for mission_id, cause in candidates:
    cur = con.execute(
        "update missions set status='pending', last_error=?, attempts=0, "
        "updated_at=datetime('now') where mission_id=?",
        (f"yeniden deneme ({cause}): düzeltmeler sonrası", mission_id),
    )
    if cur.rowcount:
        reopened.append(mission_id)
        print("  ", mission_id[:60], "|", cause)
con.commit()

print("açılan:", len(reopened))
counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print("kuyruk:", counts)
