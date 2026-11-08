import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.autonomous_company import PersistentMissionQueue
from ahos.improvement_cycle import run_cycle

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
queue = PersistentMissionQueue(R / "company-service.db")

DEPARTMENTS = [
    "data", "finance", "guvenlik", "quality", "research",
    "marketing", "sales", "support", "operations", "infrastructure",
    "holding", "creative", "software", "oyun",
]

result = run_cycle(queue, DEPARTMENTS, limit=5)
print("oluşturulan:", len(result.created))
for mission in result.created:
    print("  ", mission)
print("atlanan:", len(result.skipped))

import sqlite3

con = sqlite3.connect(R / "company-service.db")
print("kuyruk:", dict(con.execute("select status, count(*) from missions group by status").fetchall()))
