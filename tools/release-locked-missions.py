import io
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
LOCK = Path(os.environ.get("AHOS_LOCK_DIR") or Path(os.environ["LOCALAPPDATA"]) / "ahos-locks")

held = {}
if LOCK.exists():
    for path in LOCK.glob("*"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        held[path.stem] = payload

con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row
rows = list(con.execute("select mission_id, last_error from missions where status='blocked'"))

reopen = []
kept = []
for row in rows:
    text = (row["last_error"] or "").lower()
    if "proje kilidi" not in text and "kilit" not in text:
        continue
    owner = re.search(r"sahibi\s+(\S+)", row["last_error"] or "")
    owner_id = owner.group(1) if owner else ""
    pid_match = re.search(r"pid[=: ]+(\d+)", row["last_error"] or "")
    pid = int(pid_match.group(1)) if pid_match else 0
    alive = False
    if pid:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        alive = str(pid) in out.stdout
    if alive and owner_id in held:
        kept.append(row["mission_id"])
        continue
    con.execute(
        "update missions set status='pending', last_error='kilit serbest bırakıldı; yeniden deneme', updated_at=datetime('now') where mission_id=?",
        (row["mission_id"],),
    )
    reopen.append(row["mission_id"])
con.commit()

print("kilitten açılan:", len(reopen))
for mission in reopen[:12]:
    print("  ", mission[:60])
print("hâlâ kilitli:", len(kept))
counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print("durum:", counts)
