import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

os.environ["AHOS_DOCUMENT_QA"] = "1"

from ahos.owner_console import build_default_console
from ahos.queue_drain import drain

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
console = build_default_console(R)

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 2
results = drain(console, owner="dept-test-2", limit=limit)
print("islenen:", len(results))
for item in results:
    print("  ", str(item)[:160])

import sqlite3

con = sqlite3.connect(R / "company-service.db")
counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print("durum:", counts)
